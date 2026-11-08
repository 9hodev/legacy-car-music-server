"""
Network & Connection Monitoring Service
Tracks active HTTP connections, live file transfers, sliding-window throughput,
and manages background device heartbeat validation.
"""

import time
import threading
from collections import deque

class MonitorService:
    def __init__(self, db_service, server_start_time):
        self.db_service = db_service
        self.server_start_time = server_start_time
        
        # Connection tracking
        self._lock = threading.Lock()
        self.active_connections = 0
        self.connection_history = {} # ip -> {"last_seen": ..., "last_path": ..., "user_agent": ...}
        
        # Active transfers: transfer_id -> {details...}
        self.active_transfers = {}
        
        # Sliding throughput window: deque of (timestamp, uploaded_bytes, downloaded_bytes)
        self.throughput_window = deque()
        
        # Totals in this session
        self.session_uploaded_bytes = 0
        self.session_downloaded_bytes = 0
        
        # Background worker for stale devices & throughput cleanup
        self._running = True
        self._worker_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._worker_thread.start()

    def shutdown(self):
        self._running = False

    def _monitor_loop(self):
        while self._running:
            try:
                # 1. Check stale devices every 5s
                self.db_service.check_stale_devices(timeout_seconds=40)
                
                # 2. Trim throughput window older than 5s
                now = time.time()
                with self._lock:
                    while self.throughput_window and (now - self.throughput_window[0][0] > 5.0):
                        self.throughput_window.popleft()
            except Exception as e:
                print(f"[Monitor Loop Error]: {e}")
            time.sleep(5)

    # ------------------------------------------------------------------
    # HTTP Connection Lifecycle
    # ------------------------------------------------------------------
    def on_connection_start(self, client_ip, method, path, user_agent=""):
        with self._lock:
            self.active_connections += 1
            self.connection_history[client_ip] = {
                "last_seen": time.time(),
                "last_path": path,
                "method": method,
                "user_agent": user_agent[:120] if user_agent else ""
            }

    def on_connection_end(self, client_ip, bytes_sent=0, bytes_received=0):
        with self._lock:
            self.active_connections = max(0, self.active_connections - 1)
            now = time.time()
            if bytes_sent > 0 or bytes_received > 0:
                self.throughput_window.append((now, bytes_received, bytes_sent))
                self.session_uploaded_bytes += bytes_received
                self.session_downloaded_bytes += bytes_sent

    # ------------------------------------------------------------------
    # File Transfer Tracking (Separate from polling/heartbeats)
    # ------------------------------------------------------------------
    def start_transfer(self, transfer_id, transfer_type, client_ip, filename, total_bytes, device_id=None):
        now = time.time()
        record = {
            "id": transfer_id,
            "type": transfer_type, # "upload" or "download"
            "client_ip": client_ip,
            "device_id": device_id,
            "filename": filename,
            "total_bytes": total_bytes,
            "transferred_bytes": 0,
            "start_time": now,
            "last_update": now,
            "speed": 0,
            "eta": 0,
            "progress": 0.0
        }
        with self._lock:
            self.active_transfers[transfer_id] = record

        # Record in DB
        self.db_service.create_transfer(transfer_id, transfer_type, device_id, client_ip, filename, total_bytes)
        self.db_service.log_event(
            f"{transfer_type}_started",
            client_ip,
            device_id=device_id,
            filename=filename,
            file_size=total_bytes,
            status="info"
        )

    def update_transfer(self, transfer_id, current_transferred_bytes):
        now = time.time()
        with self._lock:
            t = self.active_transfers.get(transfer_id)
            if t:
                delta_bytes = current_transferred_bytes - t["transferred_bytes"]
                elapsed = now - t["last_update"]
                t["transferred_bytes"] = current_transferred_bytes
                
                if elapsed > 0.3:
                    speed = delta_bytes / elapsed if elapsed > 0 else 0
                    t["speed"] = round(speed, 1)
                    t["last_update"] = now
                    remaining_bytes = max(0, t["total_bytes"] - current_transferred_bytes)
                    t["eta"] = round(remaining_bytes / speed, 1) if speed > 0 else 0

                if t["total_bytes"] > 0:
                    t["progress"] = min(100.0, round((current_transferred_bytes / t["total_bytes"]) * 100.0, 1))

        # Update DB periodically
        self.db_service.update_transfer_progress(transfer_id, current_transferred_bytes)

    def end_transfer(self, transfer_id, status="completed", error=None):
        with self._lock:
            t = self.active_transfers.pop(transfer_id, None)

        if t:
            self.db_service.finish_transfer(transfer_id, status=status, error=error)
            event_type = f"{t['type']}_{status}"
            self.db_service.log_event(
                event_type,
                t["client_ip"],
                device_id=t.get("device_id"),
                filename=t["filename"],
                file_size=t["total_bytes"],
                status="success" if status == "completed" else "failed",
                error_details=error
            )

    # ------------------------------------------------------------------
    # Stats & Metrics for Dashboard
    # ------------------------------------------------------------------
    def get_dashboard_metrics(self):
        now = time.time()
        uptime_seconds = int(now - self.server_start_time)
        
        # Calculate throughput from sliding window (last 5s)
        total_up_5s = 0
        total_down_5s = 0
        window_duration = 1.0

        with self._lock:
            if self.throughput_window:
                window_duration = max(1.0, min(5.0, now - self.throughput_window[0][0]))
                for ts, up, down in self.throughput_window:
                    total_up_5s += up
                    total_down_5s += down

            upload_speed = round(total_up_5s / window_duration, 1)
            download_speed = round(total_down_5s / window_duration, 1)

            active_transfers_list = list(self.active_transfers.values())
            active_uploads = sum(1 for t in active_transfers_list if t["type"] == "upload")
            active_downloads = sum(1 for t in active_transfers_list if t["type"] == "download")
            active_conn_count = self.active_connections

        # Get DB totals
        db_totals = self.db_service.get_transfer_totals()
        devices = self.db_service.get_devices()
        online_devices = sum(1 for d in devices if d["online_status"])

        # Format uptime
        days = uptime_seconds // 86400
        hours = (uptime_seconds % 86400) // 3600
        mins = (uptime_seconds % 3600) // 60
        secs = uptime_seconds % 60
        uptime_str = f"{hours:02d}h {mins:02d}m {secs:02d}s"
        if days > 0:
            uptime_str = f"{days}d " + uptime_str

        return {
            "server_status": "Running",
            "uptime_seconds": uptime_seconds,
            "uptime_formatted": uptime_str,
            "active_connections": active_conn_count,
            "online_device_count": online_devices,
            "total_registered_devices": len(devices),
            "active_uploads": active_uploads,
            "active_downloads": active_downloads,
            "active_transfers_count": len(active_transfers_list),
            "upload_throughput_bps": upload_speed,
            "download_throughput_bps": download_speed,
            "total_uploaded_bytes": db_totals["total_uploaded_bytes"],
            "total_downloaded_bytes": db_totals["total_downloaded_bytes"],
            "session_uploaded_bytes": self.session_uploaded_bytes,
            "session_downloaded_bytes": self.session_downloaded_bytes,
            "active_transfers": active_transfers_list
        }

