"""
Authentication & Security Service
Provides PBKDF2-HMAC password hashing, session tokens, constant-time comparison,
and IP-based rate limiting to protect administrative actions.
"""

import os
import time
import hmac
import hashlib
import uuid
import threading

class AuthService:
    def __init__(self, db_service, default_pin="8888", default_password="admin"):
        self.db_service = db_service
        self.default_pin = default_pin
        self.default_password = default_password
        
        # In-memory sessions: session_token -> {"ip": ..., "expires": ...}
        self.sessions = {}
        self.session_lock = threading.Lock()
        
        # Rate limiting: client_ip -> [failed_timestamps]
        self.failed_attempts = {}
        self.rate_lock = threading.Lock()
        
        self._init_admin_credentials()

    def _hash_credential(self, text, salt):
        return hashlib.pbkdf2_hmac("sha256", text.encode("utf-8"), salt.encode("utf-8"), 100000).hex()

    def _init_admin_credentials(self):
        conn = self.db_service.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT salt FROM admin_auth WHERE id = 1")
        row = cur.fetchone()

        salt = row["salt"] if row else os.urandom(16).hex()
        pwd_hash = self._hash_credential(self.default_password, salt)
        pin_hash = self._hash_credential(self.default_pin, salt)

        with conn:
            conn.execute("""
            INSERT INTO admin_auth (id, salt, password_hash, pin_hash, updated_at)
            VALUES (1, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                salt = excluded.salt,
                password_hash = excluded.password_hash,
                pin_hash = excluded.pin_hash,
                updated_at = excluded.updated_at
            """, (salt, pwd_hash, pin_hash, time.time()))

    def is_rate_limited(self, client_ip):
        """Check if client IP has exceeded maximum failed attempts (5 in 5 mins)."""
        now = time.time()
        with self.rate_lock:
            attempts = self.failed_attempts.get(client_ip, [])
            # filter within 5 minutes
            recent = [t for t in attempts if now - t < 300]
            self.failed_attempts[client_ip] = recent
            
            if len(recent) >= 5:
                # locked out for 60 seconds from the 5th attempt
                if now - recent[-1] < 60:
                    return True
        return False

    def record_auth_failure(self, client_ip):
        now = time.time()
        with self.rate_lock:
            if client_ip not in self.failed_attempts:
                self.failed_attempts[client_ip] = []
            self.failed_attempts[client_ip].append(now)

    def clear_auth_failures(self, client_ip):
        with self.rate_lock:
            self.failed_attempts.pop(client_ip, None)

    def verify_credentials(self, secret, client_ip):
        """
        Verify PIN or Password using constant-time string comparison.
        Returns session_token on success, None on failure.
        """
        if self.is_rate_limited(client_ip):
            self.db_service.log_event("auth_failed", client_ip, status="warning", error_details="Rate limited (Too many attempts)")
            return None, "Rate limit exceeded. Please wait 1 minute before trying again."

        conn = self.db_service.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT salt, password_hash, pin_hash FROM admin_auth WHERE id = 1")
        row = cur.fetchone()

        if not row:
            return None, "Authentication service uninitialized."

        salt = row["salt"]
        expected_pwd = row["password_hash"]
        expected_pin = row["pin_hash"]

        computed = self._hash_credential(secret, salt)

        # Constant-time comparison
        is_pwd_match = hmac.compare_digest(computed, expected_pwd)
        is_pin_match = hmac.compare_digest(computed, expected_pin)

        if is_pwd_match or is_pin_match:
            self.clear_auth_failures(client_ip)
            session_token = f"sess_{uuid.uuid4().hex}"
            now = time.time()
            
            with self.session_lock:
                self.sessions[session_token] = {
                    "client_ip": client_ip,
                    "created_at": now,
                    "expires_at": now + (24 * 3600)  # 24 hours
                }

            self.db_service.log_event("auth_success", client_ip, status="success")
            return session_token, None
        else:
            self.record_auth_failure(client_ip)
            self.db_service.log_event("auth_failed", client_ip, status="warning", error_details="Invalid PIN/Password")
            return None, "Invalid PIN or Password."

    def validate_session(self, session_token, client_ip=None):
        """Validate if a session token is active and unexpired."""
        if not session_token:
            return False

        now = time.time()
        with self.session_lock:
            sess = self.sessions.get(session_token)
            if not sess:
                return False
            if now > sess["expires_at"]:
                del self.sessions[session_token]
                return False
            return True

    def revoke_session(self, session_token):
        with self.session_lock:
            self.sessions.pop(session_token, None)

