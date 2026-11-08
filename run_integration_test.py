import urllib.request
import urllib.error
import urllib.parse
import json
import time
import subprocess
import sys
import os

TEST_PORT = 8999
BASE_URL = f"http://127.0.0.1:{TEST_PORT}"

def run_tests():
    print(f"Starting server on port {TEST_PORT}...")
    proc = subprocess.Popen([sys.executable, "server.py", str(TEST_PORT)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(1.5)

    try:
        # 1. Test GET / (Car index)
        print("Testing GET / ...")
        req = urllib.request.urlopen(f"{BASE_URL}/")
        assert req.status == 200
        html_content = req.read().decode('utf-8')
        assert "LOCAL MUSIC SERVER" in html_content
        print("  -> GET / OK")

        # 2. Test GET /admin
        print("Testing GET /admin ...")
        req = urllib.request.urlopen(f"{BASE_URL}/admin")
        assert req.status == 200
        admin_content = req.read().decode('utf-8')
        assert "Music Drop Admin" in admin_content
        print("  -> GET /admin OK")

        # 3. Test GET /style.css & /app.js
        print("Testing GET /style.css and /app.js ...")
        req_css = urllib.request.urlopen(f"{BASE_URL}/style.css")
        assert req_css.status == 200
        assert "car-body" in req_css.read().decode('utf-8')

        req_js = urllib.request.urlopen(f"{BASE_URL}/app.js")
        assert req_js.status == 200
        assert "handleFilesUpload" in req_js.read().decode('utf-8')
        print("  -> Assets OK")

        # 4. Test GET /api/files (empty initially or existing)
        print("Testing GET /api/files ...")
        req = urllib.request.urlopen(f"{BASE_URL}/api/files")
        assert req.status == 200
        data = json.loads(req.read().decode('utf-8'))
        assert data["success"] is True
        print(f"  -> GET /api/files OK (found {len(data['files'])} files)")

        # 5. Test Streaming Upload with multipart/form-data
        print("Testing POST /api/upload (mock mp3 file) ...")
        boundary = "---------------------------BoundaryTest12345"
        test_song_data = b"ID3\x03\x00\x00\x00\x00\x00\x00" + (b"A" * 1024 * 1024) # 1MB test audio
        
        body_prefix = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="Test Song.mp3"\r\n'
            f'Content-Type: audio/mpeg\r\n\r\n'
        ).encode('utf-8')
        body_suffix = f"\r\n--{boundary}--\r\n".encode('utf-8')
        full_body = body_prefix + test_song_data + body_suffix

        upload_req = urllib.request.Request(
            f"{BASE_URL}/api/upload",
            data=full_body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(len(full_body))
            },
            method="POST"
        )
        with urllib.request.urlopen(upload_req) as resp:
            assert resp.status == 200
            resp_data = json.loads(resp.read().decode('utf-8'))
            assert resp_data["success"] is True
            print("  -> POST /api/upload 1MB OK:", resp_data)

        # 6. Verify file is in /api/files and in Car Page HTML
        req = urllib.request.urlopen(f"{BASE_URL}/api/files")
        files = json.loads(req.read().decode('utf-8'))["files"]
        assert any(f["name"] == "Test Song.mp3" for f in files)
        print("  -> File presence in /api/files verified!")

        req_car = urllib.request.urlopen(f"{BASE_URL}/")
        car_html = req_car.read().decode('utf-8')
        assert "Test Song.mp3" in car_html
        assert "/download/Test%20Song.mp3" in car_html
        print("  -> File presence in Car HTML anchor verified!")

        # 7. Test Streaming Download & Range Header
        print("Testing GET /download/Test Song.mp3 ...")
        download_url = f"{BASE_URL}/download/" + urllib.parse.quote("Test Song.mp3")
        with urllib.request.urlopen(download_url) as resp:
            assert resp.status == 200
            assert resp.headers.get("Content-Type") == "audio/mpeg"
            assert "attachment" in resp.headers.get("Content-Disposition")
            downloaded = resp.read()
            assert downloaded == test_song_data
            print("  -> Exact byte download verified (1 MB)! OK")

        # Range request test
        print("Testing HTTP Range Request (bytes=0-99) ...")
        range_req = urllib.request.Request(download_url, headers={"Range": "bytes=0-99"})
        with urllib.request.urlopen(range_req) as resp:
            assert resp.status == 206
            range_bytes = resp.read()
            assert len(range_bytes) == 100
            assert range_bytes == test_song_data[:100]
            print("  -> Range request OK")

        # 8. Test 100 MB Large File Upload (Streaming without RAM bloat)
        print("Testing 100 MB Large File Streaming Upload ...")
        large_size = 100 * 1024 * 1024 # 100 MB
        # We can send it using a custom generator/file-like object or pipe to simulate streaming
        class ChunkedStream:
            def __init__(self, prefix, suffix, target_data_len):
                self.prefix = prefix
                self.suffix = suffix
                self.target_data_len = target_data_len
                self.data_sent = 0
                self.pos = 0
                self.chunk = b"X" * (64 * 1024)

            def read(self, n=-1):
                if self.pos < len(self.prefix):
                    out = self.prefix[self.pos:self.pos + n]
                    self.pos += len(out)
                    return out
                remaining_data = self.target_data_len - self.data_sent
                if remaining_data > 0:
                    to_send = min(remaining_data, len(self.chunk), n if n > 0 else len(self.chunk))
                    self.data_sent += to_send
                    return self.chunk[:to_send]
                if self.suffix:
                    out = self.suffix
                    self.suffix = b""
                    return out
                return b""

        stream_body = ChunkedStream(
            prefix=(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"large_100mb.flac\"\r\nContent-Type: audio/flac\r\n\r\n").encode('utf-8'),
            suffix=f"\r\n--{boundary}--\r\n".encode('utf-8'),
            target_data_len=large_size
        )
        total_len = len(stream_body.prefix) + large_size + len(stream_body.suffix)

        large_req = urllib.request.Request(
            f"{BASE_URL}/api/upload",
            data=stream_body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(total_len)
            },
            method="POST"
        )
        t0 = time.time()
        with urllib.request.urlopen(large_req) as resp:
            assert resp.status == 200
            resp_data = json.loads(resp.read().decode('utf-8'))
            assert resp_data["success"] is True
            print(f"  -> 100 MB upload streamed successfully in {time.time() - t0:.2f}s! Result:", resp_data)

        # Verify size on disk
        large_disk_path = os.path.join("music", "large_100mb.flac")
        assert os.path.exists(large_disk_path)
        assert os.path.getsize(large_disk_path) == large_size
        print(f"  -> Verified 100 MB file exact disk size: {os.path.getsize(large_disk_path)} bytes!")

        # 9. Test Invalid Extension Rejection
        print("Testing rejection of non-audio extension (.exe) ...")
        bad_body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="malware.exe"\r\n'
            f'Content-Type: application/octet-stream\r\n\r\n'
            f'bad content\r\n--{boundary}--\r\n'
        ).encode('utf-8')
        bad_req = urllib.request.Request(
            f"{BASE_URL}/api/upload",
            data=bad_body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "Content-Length": str(len(bad_body))},
            method="POST"
        )
        try:
            urllib.request.urlopen(bad_req)
            raise AssertionError("Server should have rejected .exe!")
        except urllib.error.HTTPError as e:
            assert e.code == 400
            err_json = json.loads(e.read().decode('utf-8'))
            assert err_json["success"] is False
            print("  -> Extension rejection OK:", err_json["error"])

        # 10. Test Path Traversal Protection
        print("Testing Path Traversal Protection ...")
        try:
            urllib.request.urlopen(f"{BASE_URL}/download/..%2F..%2Fserver.py")
            raise AssertionError("Server should have blocked path traversal!")
        except urllib.error.HTTPError as e:
            assert e.code in [403, 404]
            print(f"  -> Path traversal blocked with HTTP {e.code}! OK")

        # 11. Test Delete API
        print("Testing POST /api/delete ...")
        del_body = json.dumps({"filename": "Test Song.mp3"}).encode('utf-8')
        del_req = urllib.request.Request(
            f"{BASE_URL}/api/delete",
            data=del_body,
            headers={"Content-Type": "application/json", "Content-Length": str(len(del_body))},
            method="POST"
        )
        with urllib.request.urlopen(del_req) as resp:
            assert resp.status == 200
            del_resp = json.loads(resp.read().decode('utf-8'))
            assert del_resp["success"] is True
            assert del_resp["deleted"] == "Test Song.mp3"
            print("  -> Deleted Test Song.mp3 OK")

        # Also delete 100MB file to clean up test data
        del_100_body = json.dumps({"filename": "large_100mb.flac"}).encode('utf-8')
        del_100_req = urllib.request.Request(
            f"{BASE_URL}/api/delete",
            data=del_100_body,
            headers={"Content-Type": "application/json", "Content-Length": str(len(del_100_body))},
            method="POST"
        )
        with urllib.request.urlopen(del_100_req) as resp:
            assert resp.status == 200
            print("  -> Cleaned up 100MB test file OK")

        print("\n==========================================")
        print(">>> ALL INTEGRATION TESTS PASSED 100%! <<<")
        print("==========================================")

    finally:
        proc.terminate()
        proc.wait()

if __name__ == "__main__":
    run_tests()
