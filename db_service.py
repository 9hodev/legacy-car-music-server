"""
Database Service Module (SQLite)
Manages persistent records for devices, activity logs, transfers, server sessions, and authentication.
Uses SQLite in WAL mode with proper indexing and thread-safe operations.
"""

import os
import sqlite3
import time
import uuid
import threading
import csv
import io

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "music_server.db")

class DatabaseService:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._local = threading.local()
        self._init_lock = threading.Lock()
        self.init_database()

    def get_connection(self):
        """Thread-local connection for safe concurrent database access."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA busy_timeout = 30000;")
            self._local.conn = conn
        return self._local.conn

    def init_database(self):
        """Initialize tables and indexes."""
        with self._init_lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA journal_mode=WAL;")
            cur = conn.cursor()

            # 1. Devices Table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                device_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                device_type TEXT NOT NULL,
                ip_address TEXT NOT NULL,
                token TEXT NOT NULL,
                first_seen REAL NOT NULL,
                last_seen REAL NOT NULL,
                online_status INTEGER NOT NULL DEFAULT 1,
                current_activity TEXT NOT NULL DEFAULT 'Idle',
                revoked INTEGER NOT NULL DEFAULT 0
            );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_devices_last_seen ON devices(last_seen);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_devices_online ON devices(online_status);")

            # 2. Activity Logs Table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                event_type TEXT NOT NULL,
                device_id TEXT,
                client_ip TEXT NOT NULL,
                filename TEXT,
                file_size INTEGER,
                status TEXT NOT NULL DEFAULT 'info',
                error_details TEXT
            );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON activity_logs(timestamp);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_logs_event_type ON activity_logs(event_type);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_logs_device_id ON activity_logs(device_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_logs_client_ip ON activity_logs(client_ip);")

            # 3. Transfers Table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS transfers (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                device_id TEXT,
                client_ip TEXT NOT NULL,
                filename TEXT NOT NULL,
                total_bytes INTEGER NOT NULL DEFAULT 0,
                transferred_bytes INTEGER NOT NULL DEFAULT 0,
                start_time REAL NOT NULL,
                end_time REAL,
                status TEXT NOT NULL DEFAULT 'in_progress',
                error TEXT
            );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_transfers_status ON transfers(status);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_transfers_start_time ON transfers(start_time);")

            # 4. Server Sessions Table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS server_sessions (
                session_id TEXT PRIMARY KEY,
                start_time REAL NOT NULL,
                end_time REAL,
                total_uploads INTEGER NOT NULL DEFAULT 0,
                total_downloads INTEGER NOT NULL DEFAULT 0
            );
            """)

            # 5. Admin Auth Table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS admin_auth (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                pin_hash TEXT NOT NULL,
                updated_at REAL NOT NULL
            );
            """)

            conn.commit()
            conn.close()

    # ------------------------------------------------------------------
    # Server Session Tracking
    # ------------------------------------------------------------------
    def start_session(self, session_id):
        conn = self.get_connection()
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO server_sessions (session_id, start_time) VALUES (?, ?)",
                (session_id, time.time())
            )

    def close_session(self, session_id):
        conn = self.get_connection()
        with conn:
            conn.execute(
                "UPDATE server_sessions SET end_time = ? WHERE session_id = ?",
                (time.time(), session_id)
            )

    # ------------------------------------------------------------------
    # Activity Logging
    # ------------------------------------------------------------------
    def log_event(self, event_type, client_ip, device_id=None, filename=None, file_size=None, status="info", error_details=None):
        conn = self.get_connection()
        now = time.time()
        try:
            with conn:
                conn.execute("""
                INSERT INTO activity_logs (timestamp, event_type, device_id, client_ip, filename, file_size, status, error_details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (now, event_type, device_id, client_ip, filename, file_size, status, error_details))
        except Exception as e:
            print(f"[DB Error] Failed to log event {event_type}: {e}")

    def get_logs(self, page=1, limit=20, event_type=None, search=None, start_date=None, end_date=None):
        conn = self.get_connection()
        query = "SELECT * FROM activity_logs WHERE 1=1"
        params = []

        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)

        if search:
            query += " AND (filename LIKE ? OR client_ip LIKE ? OR device_id LIKE ? OR error_details LIKE ?)"
            term = f"%{search}%"
            params.extend([term, term, term, term])

        if start_date:
            query += " AND timestamp >= ?"
            params.append(float(start_date))

        if end_date:
            query += " AND timestamp <= ?"
            params.append(float(end_date))

        # Count total
        count_query = query.replace("SELECT *", "SELECT COUNT(*)", 1)
        cur = conn.cursor()
        cur.execute(count_query, params)
        total_count = cur.fetchone()[0]

        # Order & Paginate
        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        offset = max(0, (page - 1) * limit)
        params.extend([limit, offset])

        cur.execute(query, params)
        rows = cur.fetchall()

        logs = []
        for r in rows:
            logs.append({
                "id": r["id"],
                "timestamp": r["timestamp"],
                "timestamp_formatted": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["timestamp"])),
                "event_type": r["event_type"],
                "device_id": r["device_id"],
                "client_ip": r["client_ip"],
                "filename": r["filename"],
                "file_size": r["file_size"],
                "status": r["status"],
                "error_details": r["error_details"]
            })

        return {
            "logs": logs,
            "total": total_count,
            "page": page,
            "limit": limit,
            "total_pages": max(1, (total_count + limit - 1) // limit)
        }

    def export_logs_csv(self):
        """Export all logs to CSV format."""
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM activity_logs ORDER BY timestamp DESC")
        rows = cur.fetchall()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Timestamp", "DateTime", "EventType", "DeviceID", "ClientIP", "Filename", "FileSize", "Status", "ErrorDetails"])

        for r in rows:
            dt_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["timestamp"]))
            writer.writerow([
                r["id"],
                r["timestamp"],
                dt_str,
                r["event_type"],
                r["device_id"] or "",
                r["client_ip"],
                r["filename"] or "",
                r["file_size"] or "",
                r["status"],
                r["error_details"] or ""
            ])

        return output.getvalue()

    def clear_logs(self):
        """Clear all activity logs."""
        conn = self.get_connection()
        with conn:
            conn.execute("DELETE FROM activity_logs;")
            conn.execute("VACUUM;")
        return True

    # ------------------------------------------------------------------
    # Device Discovery & Registry
    # ------------------------------------------------------------------
    def register_device(self, device_id, name, device_type, ip_address):
        conn = self.get_connection()
        now = time.time()
        token = f"tok_{uuid.uuid4().hex}"

        with conn:
            # Check existing
            cur = conn.cursor()
            cur.execute("SELECT * FROM devices WHERE device_id = ?", (device_id,))
            existing = cur.fetchone()

            if existing:
                cur.execute("""
                UPDATE devices
                SET name = ?, device_type = ?, ip_address = ?, last_seen = ?, online_status = 1, revoked = 0
                WHERE device_id = ?
                """, (name, device_type, ip_address, now, device_id))
                token = existing["token"]
            else:
                cur.execute("""
                INSERT INTO devices (device_id, name, device_type, ip_address, token, first_seen, last_seen, online_status, current_activity, revoked)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, 'Connected', 0)
                """, (device_id, name, device_type, ip_address, token, now, now))

        return {
            "device_id": device_id,
            "name": name,
            "device_type": device_type,
            "ip_address": ip_address,
            "token": token,
            "online_status": 1
        }

    def update_heartbeat(self, device_id, current_activity="Active", ip_address=None):
        conn = self.get_connection()
        now = time.time()
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT online_status, revoked FROM devices WHERE device_id = ?", (device_id,))
            row = cur.fetchone()
            if not row:
                return False
            if row["revoked"] == 1:
                return False

            was_offline = (row["online_status"] == 0)

            if ip_address:
                cur.execute("""
                UPDATE devices
                SET last_seen = ?, online_status = 1, current_activity = ?, ip_address = ?
                WHERE device_id = ?
                """, (now, current_activity, ip_address, device_id))
            else:
                cur.execute("""
                UPDATE devices
                SET last_seen = ?, online_status = 1, current_activity = ?
                WHERE device_id = ?
                """, (now, current_activity, device_id))

        if was_offline:
            self.log_event("device_online", ip_address or "unknown", device_id=device_id, status="info")
        return True

    def check_stale_devices(self, timeout_seconds=40):
        """Mark devices offline if no heartbeat within timeout."""
        conn = self.get_connection()
        threshold = time.time() - timeout_seconds
        marked_offline = []

        with conn:
            cur = conn.cursor()
            cur.execute("""
            SELECT device_id, name, ip_address FROM devices
            WHERE online_status = 1 AND last_seen < ?
            """, (threshold,))
            stale_rows = cur.fetchall()

            for r in stale_rows:
                marked_offline.append((r["device_id"], r["name"], r["ip_address"]))

            if stale_rows:
                cur.execute("""
                UPDATE devices
                SET online_status = 0, current_activity = 'Offline'
                WHERE online_status = 1 AND last_seen < ?
                """, (threshold,))

        for dev_id, name, ip in marked_offline:
            self.log_event("device_offline", ip, device_id=dev_id, status="info")

        return len(marked_offline)

    def get_devices(self):
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM devices ORDER BY online_status DESC, last_seen DESC")
        rows = cur.fetchall()

        devices = []
        for r in rows:
            devices.append({
                "device_id": r["device_id"],
                "name": r["name"],
                "device_type": r["device_type"],
                "ip_address": r["ip_address"],
                "first_seen": r["first_seen"],
                "last_seen": r["last_seen"],
                "last_seen_formatted": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["last_seen"])),
                "online_status": bool(r["online_status"]),
                "current_activity": r["current_activity"],
                "revoked": bool(r["revoked"])
            })
        return devices

    def revoke_device(self, device_id):
        conn = self.get_connection()
        with conn:
            cur = conn.cursor()
            cur.execute("UPDATE devices SET revoked = 1, online_status = 0, current_activity = 'Revoked' WHERE device_id = ?", (device_id,))
        self.log_event("device_revoked", "server", device_id=device_id, status="warning")
        return True

    def is_device_revoked(self, device_id):
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT revoked FROM devices WHERE device_id = ?", (device_id,))
        row = cur.fetchone()
        return bool(row["revoked"]) if row else False

    # ------------------------------------------------------------------
    # Transfer Tracking
    # ------------------------------------------------------------------
    def create_transfer(self, transfer_id, transfer_type, device_id, client_ip, filename, total_bytes):
        conn = self.get_connection()
        now = time.time()
        with conn:
            conn.execute("""
            INSERT OR REPLACE INTO transfers (id, type, device_id, client_ip, filename, total_bytes, transferred_bytes, start_time, status)
            VALUES (?, ?, ?, ?, ?, ?, 0, ?, 'in_progress')
            """, (transfer_id, transfer_type, device_id, client_ip, filename, total_bytes, now))

    def update_transfer_progress(self, transfer_id, transferred_bytes):
        conn = self.get_connection()
        with conn:
            conn.execute("""
            UPDATE transfers SET transferred_bytes = ? WHERE id = ? AND status = 'in_progress'
            """, (transferred_bytes, transfer_id))

    def finish_transfer(self, transfer_id, status="completed", error=None):
        conn = self.get_connection()
        now = time.time()
        with conn:
            conn.execute("""
            UPDATE transfers SET status = ?, end_time = ?, error = ? WHERE id = ?
            """, (status, now, error, transfer_id))

    def get_transfer_totals(self):
        """Get total uploaded & downloaded bytes across history."""
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT SUM(transferred_bytes) FROM transfers WHERE type = 'upload' AND status = 'completed'")
        up_bytes = cur.fetchone()[0] or 0
        cur.execute("SELECT SUM(transferred_bytes) FROM transfers WHERE type = 'download' AND status = 'completed'")
        down_bytes = cur.fetchone()[0] or 0
        return {"total_uploaded_bytes": up_bytes, "total_downloaded_bytes": down_bytes}
