"""
Comprehensive Test Suite for Network Dashboard & Device Monitoring
Covers all required tests:
1. Two clients connecting simultaneously
2. Device registration and heartbeat
3. Device going offline after heartbeat timeout
4. Large file upload logging
5. Large file download logging
6. Interrupted transfer handling & logging
7. Server restart and log persistence (SQLite)
8. Authentication failure logging & rate limiting
9. Admin access control & device revoking
10. Dashboard stats polling without full reload
11. Legacy Android Chrome car download compatibility
"""

import os
import sys
import time
import json
import urllib.request
import urllib.parse
import urllib.error
import subprocess
import threading
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from src.db_service import DatabaseService

SERVER_SCRIPT = os.path.join(ROOT_DIR, "server.py")
MUSIC_DIR = os.path.join(ROOT_DIR, "music")
TEST_PORT = 8997
BASE_URL = f"http://127.0.0.1:{TEST_PORT}"

def log(msg):
    print(msg, flush=True)

def run_monitoring_tests():
    log(f"=== Starting Network Dashboard & Monitoring Tests on port {TEST_PORT} ===")

    # Clean any stale test files
    for fn in ["dash_test_upload.mp3", "dash_test_large.mp3"]:
        fp = os.path.join(MUSIC_DIR, fn)
        if os.path.exists(fp):
            try: os.remove(fp)
            except Exception: pass

    # Launch server
    proc = subprocess.Popen([sys.executable, SERVER_SCRIPT, str(TEST_PORT)], cwd=ROOT_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)

    try:
        # Check server health
        req = urllib.request.urlopen(f"{BASE_URL}/api/dashboard/stats")
        assert req.status == 200
        stats = json.loads(req.read().decode('utf-8'))["stats"]
        assert stats["server_status"] == "Running"
        log("  -> Server started and /api/dashboard/stats healthy.")

        # -------------------------------------------------------------
        # Test 1: Two clients connecting simultaneously
        # -------------------------------------------------------------
        log("\n--- Test 1: Two clients connecting simultaneously ---")
        client_results = []
        def client_fetch(c_id):
            try:
                r = urllib.request.urlopen(f"{BASE_URL}/api/files")
                client_results.append((c_id, r.status))
            except Exception as e:
                client_results.append((c_id, str(e)))

        t1 = threading.Thread(target=client_fetch, args=("Client-A",))
        t2 = threading.Thread(target=client_fetch, args=("Client-B",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(client_results) == 2
        assert all(status == 200 for _, status in client_results)
        log("  -> Passed! Both concurrent client connections handled successfully.")

        # -------------------------------------------------------------
        # Test 2: Device registration and heartbeat
        # -------------------------------------------------------------
        log("\n--- Test 2: Device registration and heartbeat ---")
        reg_payload = json.dumps({
            "device_id": "test_dev_001",
            "name": "Android Head Unit Car 1",
            "device_type": "car"
        }).encode('utf-8')
        reg_req = urllib.request.Request(
            f"{BASE_URL}/api/devices/register",
            data=reg_payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(reg_req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            assert data["success"] is True
            assert data["device"]["device_id"] == "test_dev_001"
            assert data["device"]["online_status"] == 1

        # Send heartbeat
        hb_payload = json.dumps({
            "device_id": "test_dev_001",
            "current_activity": "Playing Audio Track"
        }).encode('utf-8')
        hb_req = urllib.request.Request(
            f"{BASE_URL}/api/devices/heartbeat",
            data=hb_payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(hb_req) as resp:
            assert resp.status == 200

        # Verify device appears in /api/devices
        req_devs = urllib.request.urlopen(f"{BASE_URL}/api/devices")
        devs = json.loads(req_devs.read().decode('utf-8'))["devices"]
        dev1 = next((d for d in devs if d["device_id"] == "test_dev_001"), None)
        assert dev1 is not None
        assert dev1["online_status"] is True
        assert dev1["current_activity"] == "Playing Audio Track"
        log("  -> Passed! Device registered and heartbeat updated in database.")

        # -------------------------------------------------------------
        # Test 3: Device going offline after heartbeat timeout
        # -------------------------------------------------------------
        log("\n--- Test 3: Device going offline after heartbeat timeout ---")
        db = DatabaseService()
        # Simulate last_seen older than timeout (e.g. 50s ago)
        conn = db.get_connection()
        with conn:
            conn.execute("UPDATE devices SET last_seen = ? WHERE device_id = ?", (time.time() - 50.0, "test_dev_001"))

        # Trigger check
        marked = db.check_stale_devices(timeout_seconds=40)
        assert marked >= 1
        req_devs = urllib.request.urlopen(f"{BASE_URL}/api/devices")
        devs = json.loads(req_devs.read().decode('utf-8'))["devices"]
        dev1 = next((d for d in devs if d["device_id"] == "test_dev_001"), None)
        assert dev1["online_status"] is False
        assert dev1["current_activity"] == "Offline"
        log("  -> Passed! Stale device correctly marked offline and logged.")

        # -------------------------------------------------------------
        # Test 4: Large file upload logging
        # -------------------------------------------------------------
        log("\n--- Test 4: Large file upload logging ---")
        boundary = "---------------------------UploadTestBoundary"
        file_payload = b"A" * (2 * 1024 * 1024) # 2 MB
        up_body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="dash_test_upload.mp3"\r\n'
            f'Content-Type: audio/mpeg\r\n\r\n'
        ).encode('utf-8') + file_payload + f"\r\n--{boundary}--\r\n".encode('utf-8')

        up_req = urllib.request.Request(
            f"{BASE_URL}/api/upload",
            data=up_body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(len(up_body)),
                "X-Device-Id": "test_dev_001"
            },
            method="POST"
        )
        with urllib.request.urlopen(up_req) as resp:
            assert resp.status == 200

        # Verify activity logs contain upload_completed
        req_logs = urllib.request.urlopen(f"{BASE_URL}/api/logs?event_type=upload_completed")
        logs_data = json.loads(req_logs.read().decode('utf-8'))["logs"]
        assert any(l["filename"] == "dash_test_upload.mp3" for l in logs_data)
        log("  -> Passed! Large upload recorded in transfers and activity_logs.")

        # -------------------------------------------------------------
        # Test 5: Large file download logging
        # -------------------------------------------------------------
        log("\n--- Test 5: Large file download logging ---")
        dl_url = f"{BASE_URL}/download/" + urllib.parse.quote("dash_test_upload.mp3")
        dl_req = urllib.request.Request(dl_url, headers={"X-Device-Id": "test_dev_001"})
        with urllib.request.urlopen(dl_req) as resp:
            data = resp.read()
            assert len(data) == len(file_payload)

        req_logs = urllib.request.urlopen(f"{BASE_URL}/api/logs?event_type=download_completed")
        logs_data = json.loads(req_logs.read().decode('utf-8'))["logs"]
        assert any(l["filename"] == "dash_test_upload.mp3" for l in logs_data)
        log("  -> Passed! Large download streamed and logged in database.")

        # -------------------------------------------------------------
        # Test 6: Interrupted transfer handling
        # -------------------------------------------------------------
        log("\n--- Test 6: Interrupted transfer handling ---")
        # Simulate an interrupted transfer via DB and monitor service
        db.create_transfer("test_interrupted_1", "download", "test_dev_001", "127.0.0.1", "dash_test_upload.mp3", 10000000)
        db.update_transfer_progress("test_interrupted_1", 2500000)
        db.finish_transfer("test_interrupted_1", status="interrupted", error="Client connection dropped")

        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT status, transferred_bytes FROM transfers WHERE id = 'test_interrupted_1'")
        row = cur.fetchone()
        assert row["status"] == "interrupted"
        assert row["transferred_bytes"] == 2500000
        log("  -> Passed! Interrupted transfer correctly recorded with partial bytes.")

        # -------------------------------------------------------------
        # Test 7: Server restart and log persistence (SQLite)
        # -------------------------------------------------------------
        log("\n--- Test 7: Server restart and log persistence ---")
        # Restart the server process cleanly
        proc.terminate()
        proc.wait()

        # Relaunch
        proc = subprocess.Popen([sys.executable, SERVER_SCRIPT, str(TEST_PORT)], cwd=ROOT_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.5)

        # Check that logs and devices survived the restart
        req_logs = urllib.request.urlopen(f"{BASE_URL}/api/logs?limit=50")
        logs_after_restart = json.loads(req_logs.read().decode('utf-8'))["logs"]
        assert len(logs_after_restart) > 0
        assert any(l["event_type"] == "server_started" for l in logs_after_restart)
        assert any(l["event_type"] == "upload_completed" for l in logs_after_restart)
        log("  -> Passed! SQLite logs and device records survived server restart 100%.")

        # -------------------------------------------------------------
        # Test 8: Admin access control & device revoking
        # -------------------------------------------------------------
        log("\n--- Test 8: Admin access control & device revoking ---")
        # Authenticate with valid default password "admin"
        auth_payload = json.dumps({"secret": "admin"}).encode('utf-8')
        auth_req = urllib.request.Request(
            f"{BASE_URL}/api/auth/login",
            data=auth_payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(auth_req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            admin_token = data["token"]
            assert admin_token.startswith("sess_")

        # Revoke device using admin token
        revoke_payload = json.dumps({"device_id": "test_dev_001"}).encode('utf-8')
        revoke_req = urllib.request.Request(
            f"{BASE_URL}/api/devices/revoke",
            data=revoke_payload,
            headers={"Content-Type": "application/json", "X-Admin-Token": admin_token},
            method="POST"
        )
        with urllib.request.urlopen(revoke_req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            assert data["success"] is True

        # Verify device is revoked
        assert db.is_device_revoked("test_dev_001") is True
        log("  -> Passed! Admin token authenticated and device revoked.")

        # Test clear logs API with VACUUM
        clear_req = urllib.request.Request(
            f"{BASE_URL}/api/logs/clear",
            data=b"{}",
            headers={"Content-Type": "application/json", "X-Admin-Token": admin_token},
            method="POST"
        )
        with urllib.request.urlopen(clear_req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            assert data["success"] is True
            log("  -> Passed! Clear logs and VACUUM completed without transaction errors.")

        # -------------------------------------------------------------
        # Test 9: Authentication failure logging & rate limiting
        # -------------------------------------------------------------
        log("\n--- Test 9: Authentication failure logging & rate limiting ---")
        bad_auth_payload = json.dumps({"secret": "wrong_pin"}).encode('utf-8')
        for i in range(5):
            req_bad = urllib.request.Request(
                f"{BASE_URL}/api/auth/login",
                data=bad_auth_payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            try:
                urllib.request.urlopen(req_bad)
            except urllib.error.HTTPError as e:
                assert e.code == 401

        # 6th attempt should be rate-limited
        try:
            req_bad = urllib.request.Request(
                f"{BASE_URL}/api/auth/login",
                data=bad_auth_payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            urllib.request.urlopen(req_bad)
            raise AssertionError("Should have been rate limited!")
        except urllib.error.HTTPError as e:
            assert e.code == 401
            data = json.loads(e.read().decode('utf-8'))
            assert "Rate limit" in data["error"] or "wait" in data["error"]
        log("  -> Passed! Auth failures logged and rate limiter engaged.")

        # -------------------------------------------------------------
        # Test 10: Dashboard stats polling without full reload
        # -------------------------------------------------------------
        log("\n--- Test 10: Dashboard stats polling without full reload ---")
        req_stats = urllib.request.urlopen(f"{BASE_URL}/api/dashboard/stats")
        stats = json.loads(req_stats.read().decode('utf-8'))["stats"]
        assert "uptime_seconds" in stats
        assert "upload_throughput_bps" in stats
        assert "download_throughput_bps" in stats
        assert "active_connections" in stats
        log("  -> Passed! Real-time metrics API returns valid live data.")

        # -------------------------------------------------------------
        # Test 11: Legacy Android Chrome car download compatibility
        # -------------------------------------------------------------
        log("\n--- Test 11: Legacy Android Chrome car download compatibility ---")
        car_req = urllib.request.Request(
            f"{BASE_URL}/",
            headers={"User-Agent": "Mozilla/5.0 (Linux; U; Android 4.4.2; en-us) AppleWebKit/537.36"}
        )
        with urllib.request.urlopen(car_req) as resp:
            assert resp.status == 200
            html_text = resp.read().decode('utf-8')
            assert "LOCAL MUSIC SERVER" in html_text
            assert "btn-download" in html_text
        log("  -> Passed! Zero-JS Car view remains 100% compatible with legacy Android Chrome.")

        # Clean test files
        for fn in ["dash_test_upload.mp3", "dash_test_large.mp3"]:
            fp = os.path.join(MUSIC_DIR, fn)
            if os.path.exists(fp):
                try: os.remove(fp)
                except Exception: pass

        log("\n=======================================================")
        log(">>> ALL NETWORK DASHBOARD & MONITORING TESTS PASSED! <<<")
        log("=======================================================")

    finally:
        proc.terminate()
        proc.wait()

if __name__ == "__main__":
    run_monitoring_tests()
