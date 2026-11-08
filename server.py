#!/usr/bin/env python3
"""
Local Music Drop Server & Audio Studio
A lightweight, zero-dependency HTTP server built with Python 3 Standard Library
and FFmpeg audio processing engine.
"""

import os
import sys
import re
import json
import socket
import subprocess
import platform
import urllib.parse
from http import HTTPStatus
import http.server
import socketserver
import time
import html

from audio_service import AudioService
from audio_convert import (
    SUPPORTED_INPUT_EXTS,
    SUPPORTED_OUTPUT_EXTS,
    is_lossy_transcode
)

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
DEFAULT_PORT = 8000
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MUSIC_DIR = os.path.join(BASE_DIR, "music")
ALLOWED_EXTENSIONS = {".mp3", ".m4a", ".aac", ".flac", ".wav", ".ogg", ".opus"}

MIME_TYPES = {
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".flac": "audio/flac",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".opus": "audio/opus",
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".ico": "image/x-icon",
    ".png": "image/png",
    ".svg": "image/svg+xml",
}

# Ensure music directory exists
os.makedirs(MUSIC_DIR, exist_ok=True)

# Initialize Audio Service (Background workers for FFmpeg convert/merge)
audio_service = AudioService(MUSIC_DIR, max_workers=2)


# ----------------------------------------------------------------------
# Helper Utilities
# ----------------------------------------------------------------------
def format_size(bytes_num):
    """Format bytes to human readable string (KB, MB, GB)."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_num < 1024.0:
            return f"{bytes_num:.1f} {unit}" if unit != 'B' else f"{bytes_num} B"
        bytes_num /= 1024.0
    return f"{bytes_num:.1f} TB"


def sanitize_filename(filename):
    """
    Sanitize filename to prevent path traversal and illegal characters,
    while preserving unicode characters (Thai, Japanese, accented characters, etc.).
    """
    filename = os.path.basename(filename)
    filename = re.sub(r'[\x00-\x1f\x7f/\\:\*\?"<>\|]', '', filename).strip()
    filename = filename.lstrip('. ')
    if not filename:
        filename = f"audio_{int(time.time())}.mp3"
    return filename


def get_unique_filename(directory, filename):
    """Ensure filename does not overwrite existing file by appending (1), (2), etc."""
    base, ext = os.path.splitext(filename)
    target = os.path.join(directory, filename)
    counter = 1
    while os.path.exists(target):
        filename = f"{base} ({counter}){ext}"
        target = os.path.join(directory, filename)
        counter += 1
    return filename


def is_safe_path(base_directory, target_path):
    """Check if target_path is strictly inside base_directory to prevent traversal."""
    try:
        base = os.path.abspath(base_directory)
        target = os.path.abspath(target_path)
        return os.path.commonpath([base, target]) == base
    except Exception:
        return False


def get_network_interfaces():
    """Detect local network IP addresses."""
    interfaces = []
    seen_ips = set()

    if platform.system() == "Darwin":
        for iface in ["en0", "en1", "en2", "en3"]:
            try:
                res = subprocess.run(
                    ["ipconfig", "getifaddr", iface],
                    capture_output=True,
                    text=True,
                    timeout=1
                )
                ip = res.stdout.strip()
                if ip and ip not in seen_ips:
                    seen_ips.add(ip)
                    desc = f"Wi-Fi ({iface})" if iface in ["en0", "en1"] else iface
                    interfaces.append((desc, ip, True if iface in ["en0", "en1"] else False))
            except Exception:
                pass

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(('10.255.255.255', 1))
        routed_ip = s.getsockname()[0]
        s.close()
        if routed_ip and routed_ip not in seen_ips and not routed_ip.startswith("127."):
            seen_ips.add(routed_ip)
            interfaces.append(("Active Network", routed_ip, True))
    except Exception:
        pass

    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if ip not in seen_ips and not ip.startswith("127."):
                seen_ips.add(ip)
                interfaces.append(("Local IP", ip, False))
    except Exception:
        pass

    interfaces.append(("Localhost", "127.0.0.1", False))
    return interfaces


def get_music_files_list(include_metadata=False):
    """Scan music/ folder and return sorted file info list."""
    files = []
    try:
        for entry in os.scandir(MUSIC_DIR):
            if entry.is_file() and not entry.name.startswith("."):
                ext = os.path.splitext(entry.name)[1].lower()
                if ext in ALLOWED_EXTENSIONS:
                    stat = entry.stat()
                    item = {
                        "name": entry.name,
                        "size": stat.st_size,
                        "size_formatted": format_size(stat.st_size),
                        "mtime": stat.st_mtime,
                        "url": f"/download/{urllib.parse.quote(entry.name)}",
                        "is_locked": audio_service.is_file_locked(entry.name)
                    }
                    if include_metadata:
                        meta = audio_service.get_audio_metadata(entry.path)
                        item.update({
                            "duration": meta.get("duration", 0.0),
                            "duration_formatted": meta.get("duration_formatted", "00:00"),
                            "format": meta.get("format", ext.lstrip('.')),
                            "bitrate": meta.get("bitrate", 0),
                            "sample_rate": meta.get("sample_rate", 0),
                            "channels": meta.get("channels", 0)
                        })
                    files.append(item)
    except Exception as e:
        print(f"[Error] Failed to scan music directory: {e}", file=sys.stderr)

    files.sort(key=lambda x: x["name"].lower())
    return files


# ----------------------------------------------------------------------
# Streaming Multipart Form Data Parser
# ----------------------------------------------------------------------
def parse_streaming_multipart(stream, boundary, content_length, on_file_start, on_file_data, on_file_end):
    boundary_bytes = boundary.encode('latin1')
    first_boundary = b"--" + boundary_bytes
    delimiter = b"\r\n--" + boundary_bytes

    CHUNK_SIZE = 64 * 1024
    buffer = b""
    bytes_remaining = content_length

    def read_exact(n):
        nonlocal bytes_remaining
        if bytes_remaining <= 0 or n <= 0:
            return b""
        to_read = min(n, bytes_remaining)
        chunk = stream.read(to_read)
        bytes_remaining -= len(chunk)
        return chunk

    def read_line():
        nonlocal buffer
        while b"\r\n" not in buffer and bytes_remaining > 0:
            chunk = read_exact(CHUNK_SIZE)
            if not chunk:
                break
            buffer += chunk

        idx = buffer.find(b"\r\n")
        if idx != -1:
            line = buffer[:idx]
            buffer = buffer[idx + 2:]
            return line
        else:
            line = buffer
            buffer = b""
            return line

    line = read_line().strip()
    if line != first_boundary:
        raise ValueError(f"Invalid multipart boundary start: {line[:50]}")

    while True:
        headers = {}
        while True:
            hline = read_line()
            if not hline:
                break
            try:
                decoded = hline.decode('latin1')
            except Exception:
                decoded = hline.decode('utf-8', errors='replace')
            if ':' in decoded:
                k, v = decoded.split(':', 1)
                headers[k.strip().lower()] = v.strip()

        cd = headers.get('content-disposition', '')
        filename = None

        m_fn = re.search(r'filename="([^"]*)"', cd)
        if m_fn:
            filename = m_fn.group(1)
        elif "filename*=" in cd:
            m_fn_star = re.search(r"filename\*=(?:UTF-8''|utf-8'')([^;]+)", cd)
            if m_fn_star:
                filename = urllib.parse.unquote(m_fn_star.group(1))

        is_file = (filename is not None and len(filename) > 0)

        if is_file:
            on_file_start(filename, headers)

        delim_len = len(delimiter)
        while True:
            idx = buffer.find(delimiter)
            if idx != -1:
                part_data = buffer[:idx]
                if is_file and part_data:
                    on_file_data(part_data)
                if is_file:
                    on_file_end()

                buffer = buffer[idx + delim_len:]
                while len(buffer) < 2 and bytes_remaining > 0:
                    chunk = read_exact(CHUNK_SIZE)
                    if not chunk:
                        break
                    buffer += chunk

                if buffer.startswith(b"--"):
                    return
                elif buffer.startswith(b"\r\n"):
                    buffer = buffer[2:]
                    break
                else:
                    nl_idx = buffer.find(b"\r\n")
                    if nl_idx != -1:
                        buffer = buffer[nl_idx + 2:]
                    break
            else:
                if len(buffer) >= delim_len:
                    safe_len = len(buffer) - delim_len + 1
                    safe_data = buffer[:safe_len]
                    buffer = buffer[safe_len:]
                    if is_file and safe_data:
                        on_file_data(safe_data)

                chunk = read_exact(CHUNK_SIZE)
                if not chunk:
                    if is_file and buffer:
                        on_file_data(buffer)
                        on_file_end()
                    return
                buffer += chunk


# ----------------------------------------------------------------------
# HTTP Request Handler
# ----------------------------------------------------------------------
class LocalMusicRequestHandler(http.server.BaseHTTPRequestHandler):
    server_version = "LocalMusicServer/2.0"

    def log_message(self, format, *args):
        sys.stdout.write(f"[{time.strftime('%H:%M:%S')}] {self.address_string()} - {format % args}\n")
        sys.stdout.flush()

    def send_json(self, data, status=HTTPStatus.OK):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, message, status=HTTPStatus.BAD_REQUEST):
        self.send_json({"success": False, "error": message}, status=status)

    def read_json_body(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 0:
                return None
            body = self.rfile.read(content_length).decode('utf-8')
            return json.loads(body)
        except Exception:
            return None

    def serve_static_file(self, file_path, mime_type):
        if not os.path.isfile(file_path):
            self.send_error(HTTPStatus.NOT_FOUND, "File Not Found")
            return

        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, f"Error reading file: {e}")

    def render_car_index(self):
        index_path = os.path.join(BASE_DIR, "index.html")
        if not os.path.isfile(index_path):
            self.send_error(HTTPStatus.NOT_FOUND, "index.html not found")
            return

        try:
            with open(index_path, "r", encoding="utf-8") as f:
                template = f.read()

            files = get_music_files_list()

            if not files:
                html_items = (
                    '<div class="empty-state">'
                    '  <p class="empty-title">No Music Files Found</p>'
                    '  <p class="empty-desc">Open the Admin page on your Mac to upload songs.</p>'
                    '</div>'
                )
            else:
                items = []
                for file_info in files:
                    safe_name = html.escape(file_info["name"])
                    raw_url = file_info["url"]
                    safe_size = file_info["size_formatted"]
                    items.append(
                        f'<div class="song-card">\n'
                        f'  <div class="song-info">\n'
                        f'    <div class="song-title">{safe_name}</div>\n'
                        f'    <div class="song-size">{safe_size}</div>\n'
                        f'  </div>\n'
                        f'  <a class="btn-download" href="{raw_url}" download="{safe_name}">DOWNLOAD</a>\n'
                        f'</div>'
                    )
                html_items = "\n".join(items)

            rendered = template.replace("<!-- MUSIC_ITEMS_PLACEHOLDER -->", html_items)
            rendered = rendered.replace("<!-- MUSIC_COUNT_PLACEHOLDER -->", str(len(files)))

            content_bytes = rendered.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content_bytes)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(content_bytes)
        except Exception as e:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, f"Error rendering index: {e}")

    def handle_file_download(self, raw_filename):
        filename = urllib.parse.unquote(raw_filename)
        filename = os.path.basename(filename)
        file_path = os.path.join(MUSIC_DIR, filename)

        if not is_safe_path(MUSIC_DIR, file_path) or not os.path.isfile(file_path):
            self.send_error(HTTPStatus.NOT_FOUND, "Music file not found")
            return

        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            self.send_error(HTTPStatus.FORBIDDEN, "File extension not allowed")
            return

        try:
            file_size = os.path.getsize(file_path)
            content_type = MIME_TYPES.get(ext, "application/octet-stream")

            range_header = self.headers.get("Range")
            start = 0
            end = file_size - 1

            if range_header and range_header.startswith("bytes="):
                try:
                    ranges = range_header.split("=")[1].strip().split("-")
                    if ranges[0]:
                        start = int(ranges[0])
                    if len(ranges) > 1 and ranges[1]:
                        end = int(ranges[1])
                    if start >= file_size or end >= file_size or start > end:
                        self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                        self.send_header("Content-Range", f"bytes */{file_size}")
                        self.end_headers()
                        return
                    self.send_response(HTTPStatus.PARTIAL_CONTENT)
                    self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                except Exception:
                    start = 0
                    end = file_size - 1
                    self.send_response(HTTPStatus.OK)
            else:
                self.send_response(HTTPStatus.OK)

            chunk_len = end - start + 1
            ascii_name = re.sub(r'[^\x20-\x7e]', '_', filename).replace('"', '')
            quoted_utf8_name = urllib.parse.quote(filename)
            disposition = f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{quoted_utf8_name}'

            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(chunk_len))
            self.send_header("Content-Disposition", disposition)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()

            CHUNK_SIZE = 64 * 1024
            bytes_left = chunk_len

            with open(file_path, "rb") as f:
                if start > 0:
                    f.seek(start)
                while bytes_left > 0:
                    read_bytes = min(CHUNK_SIZE, bytes_left)
                    data = f.read(read_bytes)
                    if not data:
                        break
                    self.wfile.write(data)
                    bytes_left -= len(data)

        except (ConnectionResetError, BrokenPipeError):
            pass
        except Exception as e:
            print(f"[Error] Stream error for {filename}: {e}", file=sys.stderr)

    # ------------------------------------------------------------------
    # GET Router
    # ------------------------------------------------------------------
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ["/", "/index.html"]:
            self.render_car_index()
        elif path in ["/admin", "/admin.html"]:
            self.serve_static_file(os.path.join(BASE_DIR, "admin.html"), "text/html; charset=utf-8")
        elif path in ["/studio", "/studio.html"]:
            self.serve_static_file(os.path.join(BASE_DIR, "studio.html"), "text/html; charset=utf-8")
        elif path == "/style.css":
            self.serve_static_file(os.path.join(BASE_DIR, "style.css"), "text/css; charset=utf-8")
        elif path == "/app.js":
            self.serve_static_file(os.path.join(BASE_DIR, "app.js"), "application/javascript; charset=utf-8")
        elif path == "/studio.js":
            self.serve_static_file(os.path.join(BASE_DIR, "studio.js"), "application/javascript; charset=utf-8")
        elif path == "/api/files":
            query = urllib.parse.parse_qs(parsed.query)
            include_meta = "meta" in query and query["meta"][0] in ["1", "true"]
            files = get_music_files_list(include_metadata=include_meta)
            self.send_json({
                "success": True,
                "files": files,
                "count": len(files),
                "ffmpeg_available": audio_service.is_available()
            })
        elif path.startswith("/api/tasks/"):
            task_id = path[len("/api/tasks/"):]
            task = audio_service.get_task(task_id)
            if not task:
                self.send_error_json("Task not found", status=HTTPStatus.NOT_FOUND)
            else:
                self.send_json({"success": True, "task": task})
        elif path.startswith("/download/"):
            raw_filename = path[len("/download/"):]
            self.handle_file_download(raw_filename)
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    # ------------------------------------------------------------------
    # POST Router (Upload, Delete, Rename, Convert, Merge)
    # ------------------------------------------------------------------
    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ["/api/upload", "/upload"]:
            self.handle_upload()
        elif path in ["/api/delete", "/delete"]:
            self.handle_delete()
        elif path in ["/api/rename", "/rename"]:
            self.handle_rename()
        elif path in ["/api/convert", "/convert"]:
            self.handle_convert()
        elif path in ["/api/merge", "/merge"]:
            self.handle_merge()
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")

    def handle_upload(self):
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type or "boundary=" not in content_type:
            self.send_error_json("Invalid Content-Type: multipart/form-data required")
            return

        boundary = content_type.split("boundary=")[1].strip()
        if boundary.startswith('"') and boundary.endswith('"'):
            boundary = boundary[1:-1]

        try:
            content_length = int(self.headers.get("Content-Length", 0))
        except (ValueError, TypeError):
            self.send_error_json("Invalid Content-Length header")
            return

        if content_length <= 0:
            self.send_error_json("Content-Length must be greater than zero")
            return

        uploaded_files = []
        current_file = {
            "handle": None,
            "temp_path": None,
            "final_name": None,
            "bytes_written": 0,
            "error": None
        }

        def on_file_start(raw_name, headers):
            safe_name = sanitize_filename(raw_name)
            ext = os.path.splitext(safe_name)[1].lower()

            if ext not in ALLOWED_EXTENSIONS:
                current_file["error"] = f"Extension '{ext}' not allowed. Supported: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
                return

            unique_name = get_unique_filename(MUSIC_DIR, safe_name)
            temp_name = f".tmp_{time.time_ns()}_{unique_name}"
            temp_path = os.path.join(MUSIC_DIR, temp_name)

            try:
                current_file["handle"] = open(temp_path, "wb")
                current_file["temp_path"] = temp_path
                current_file["final_name"] = unique_name
                current_file["bytes_written"] = 0
                current_file["error"] = None
            except Exception as e:
                current_file["error"] = f"Failed to create file on disk: {e}"

        def on_file_data(chunk):
            if current_file["handle"] and not current_file["error"]:
                try:
                    current_file["handle"].write(chunk)
                    current_file["bytes_written"] += len(chunk)
                except Exception as e:
                    current_file["error"] = f"Write error: {e}"

        def on_file_end():
            if current_file["handle"]:
                try:
                    current_file["handle"].close()
                except Exception:
                    pass
                current_file["handle"] = None

            if current_file["error"]:
                if current_file["temp_path"] and os.path.exists(current_file["temp_path"]):
                    try:
                        os.remove(current_file["temp_path"])
                    except Exception:
                        pass
                uploaded_files.append({
                    "name": current_file.get("final_name") or "unknown",
                    "success": False,
                    "error": current_file["error"]
                })
            elif current_file["temp_path"]:
                final_path = os.path.join(MUSIC_DIR, current_file["final_name"])
                try:
                    os.replace(current_file["temp_path"], final_path)
                    uploaded_files.append({
                        "name": current_file["final_name"],
                        "size": current_file["bytes_written"],
                        "size_formatted": format_size(current_file["bytes_written"]),
                        "success": True,
                        "url": f"/download/{urllib.parse.quote(current_file['final_name'])}"
                    })
                except Exception as e:
                    if os.path.exists(current_file["temp_path"]):
                        os.remove(current_file["temp_path"])
                    uploaded_files.append({
                        "name": current_file["final_name"],
                        "success": False,
                        "error": str(e)
                    })

        try:
            parse_streaming_multipart(
                self.rfile,
                boundary,
                content_length,
                on_file_start,
                on_file_data,
                on_file_end
            )
        except Exception as e:
            if current_file.get("handle"):
                current_file["handle"].close()
            if current_file.get("temp_path") and os.path.exists(current_file["temp_path"]):
                try:
                    os.remove(current_file["temp_path"])
                except Exception:
                    pass
            self.send_error_json(f"Streaming upload failed: {e}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        success_count = sum(1 for f in uploaded_files if f.get("success"))
        if success_count == 0 and uploaded_files:
            first_err = uploaded_files[0].get("error", "Upload failed")
            self.send_error_json(first_err, status=HTTPStatus.BAD_REQUEST)
        else:
            self.send_json({
                "success": True,
                "message": f"Successfully uploaded {success_count} file(s)",
                "files": uploaded_files
            })

    def handle_delete(self):
        data = self.read_json_body()
        if not data:
            self.send_error_json("Invalid JSON body")
            return

        filename = data.get("filename", "").strip()
        if not filename:
            self.send_error_json("Filename is required")
            return

        filename = os.path.basename(filename)
        target_path = os.path.join(MUSIC_DIR, filename)

        if not is_safe_path(MUSIC_DIR, target_path):
            self.send_error_json("Invalid path: traversal detected", status=HTTPStatus.FORBIDDEN)
            return

        if not os.path.isfile(target_path):
            self.send_error_json("File not found on server", status=HTTPStatus.NOT_FOUND)
            return

        # Check if file is locked by an ongoing conversion or merge task
        if audio_service.is_file_locked(filename):
            self.send_error_json(
                f"Cannot delete '{filename}': File is currently being processed by an active task.",
                status=HTTPStatus.CONFLICT
            )
            return

        try:
            os.remove(target_path)
            self.send_json({"success": True, "message": f"Deleted {filename}", "deleted": filename})
        except Exception as e:
            self.send_error_json(f"Failed to delete file: {e}", status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def handle_rename(self):
        """
        Rename audio file preserving original extension.
        Prevents path traversal, duplicate names, and renaming locked files.
        """
        data = self.read_json_body()
        if not data:
            self.send_error_json("Invalid JSON body")
            return

        old_name = data.get("old_name", "").strip()
        new_name = data.get("new_name", "").strip()

        if not old_name or not new_name:
            self.send_error_json("Both old_name and new_name are required")
            return

        old_name = os.path.basename(old_name)
        old_path = os.path.join(MUSIC_DIR, old_name)

        if not is_safe_path(MUSIC_DIR, old_path) or not os.path.isfile(old_path):
            self.send_error_json("Original file not found", status=HTTPStatus.NOT_FOUND)
            return

        if audio_service.is_file_locked(old_name):
            self.send_error_json(
                f"Cannot rename '{old_name}': File is currently being processed by an active task.",
                status=HTTPStatus.CONFLICT
            )
            return

        # Preserve the original audio format extension!
        old_base, old_ext = os.path.splitext(old_name)
        new_base, new_ext = os.path.splitext(new_name)

        # If user included an extension in new_name, strip it if different or keep base
        sanitized_base = sanitize_filename(new_base if new_ext.lower() == old_ext.lower() else new_name)
        # Strip any accidental extension in sanitized_base
        sanitized_base = os.path.splitext(sanitized_base)[0]

        if not sanitized_base:
            self.send_error_json("New filename cannot be empty")
            return

        final_new_name = f"{sanitized_base}{old_ext}"
        new_path = os.path.join(MUSIC_DIR, final_new_name)

        if not is_safe_path(MUSIC_DIR, new_path):
            self.send_error_json("Invalid new filename", status=HTTPStatus.FORBIDDEN)
            return

        if final_new_name != old_name and os.path.exists(new_path):
            self.send_error_json(f"A file named '{final_new_name}' already exists", status=HTTPStatus.CONFLICT)
            return

        try:
            os.rename(old_path, new_path)
            self.send_json({
                "success": True,
                "message": f"Renamed to {final_new_name}",
                "old_name": old_name,
                "new_name": final_new_name
            })
        except Exception as e:
            self.send_error_json(f"Failed to rename file: {e}", status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def handle_convert(self):
        """
        Submit background audio conversion / optimization task.
        """
        if not audio_service.is_available():
            self.send_error_json(
                "FFmpeg is not available on this server. Please install FFmpeg (e.g., 'brew install ffmpeg' on macOS).",
                status=HTTPStatus.SERVICE_UNAVAILABLE
            )
            return

        data = self.read_json_body()
        if not data:
            self.send_error_json("Invalid JSON body")
            return

        src_filename = os.path.basename(data.get("source_filename", "").strip())
        out_format = data.get("output_format", "mp3").lower().lstrip('.')
        bitrate = data.get("bitrate", "192k").strip()
        sample_rate = data.get("sample_rate")
        channels = data.get("channels")
        overwrite = bool(data.get("overwrite", False))

        target_custom = data.get("target_filename", "").strip()

        if not src_filename:
            self.send_error_json("source_filename is required")
            return

        src_path = os.path.join(MUSIC_DIR, src_filename)
        if not is_safe_path(MUSIC_DIR, src_path) or not os.path.isfile(src_path):
            self.send_error_json("Source file not found", status=HTTPStatus.NOT_FOUND)
            return

        out_ext = f".{out_format}"
        if out_ext not in SUPPORTED_OUTPUT_EXTS:
            self.send_error_json(f"Unsupported output format: {out_format}")
            return

        if target_custom:
            target_base = os.path.splitext(os.path.basename(target_custom))[0]
            sanitized_target = f"{sanitize_filename(target_base)}{out_ext}"
        else:
            src_base = os.path.splitext(src_filename)[0]
            if overwrite and out_ext == os.path.splitext(src_filename)[1].lower():
                sanitized_target = src_filename
            else:
                sanitized_target = f"{src_base}_opt{out_ext}"

        if not overwrite:
            sanitized_target = get_unique_filename(MUSIC_DIR, sanitized_target)

        options = {
            "output_format": out_format,
            "bitrate": bitrate,
            "sample_rate": sample_rate,
            "channels": channels
        }

        try:
            task_id = audio_service.submit_convert_task(
                source_filename=src_filename,
                target_filename=sanitized_target,
                options=options,
                overwrite=overwrite
            )
            task = audio_service.get_task(task_id)
            self.send_json({
                "success": True,
                "task_id": task_id,
                "task": task,
                "message": "Conversion task started in background"
            })
        except Exception as e:
            self.send_error_json(str(e), status=HTTPStatus.BAD_REQUEST)

    def handle_merge(self):
        """
        Submit background audio merge task (with concat, silence, or crossfade).
        """
        if not audio_service.is_available():
            self.send_error_json(
                "FFmpeg is not available on this server. Please install FFmpeg (e.g., 'brew install ffmpeg' on macOS).",
                status=HTTPStatus.SERVICE_UNAVAILABLE
            )
            return

        data = self.read_json_body()
        if not data:
            self.send_error_json("Invalid JSON body")
            return

        src_filenames = [os.path.basename(f.strip()) for f in data.get("source_filenames", []) if f.strip()]
        if len(src_filenames) < 2:
            self.send_error_json("Please provide at least 2 source files to merge")
            return

        out_format = data.get("output_format", "mp3").lower().lstrip('.')
        out_ext = f".{out_format}"
        if out_ext not in SUPPORTED_OUTPUT_EXTS:
            self.send_error_json(f"Unsupported output format: {out_format}")
            return

        target_name = data.get("target_filename", "").strip()
        if target_name:
            base = os.path.splitext(os.path.basename(target_name))[0]
            target_name = f"{sanitize_filename(base)}{out_ext}"
        else:
            target_name = f"merged_{int(time.time())}{out_ext}"

        # Never overwrite existing file during merge
        target_name = get_unique_filename(MUSIC_DIR, target_name)

        options = {
            "output_format": out_format,
            "bitrate": data.get("bitrate", "192k"),
            "sample_rate": data.get("sample_rate", 44100),
            "channels": data.get("channels", 2),
            "crossfade": float(data.get("crossfade", 0.0)),
            "silence": float(data.get("silence", 0.0))
        }

        try:
            task_id = audio_service.submit_merge_task(
                source_filenames=src_filenames,
                target_filename=target_name,
                options=options
            )
            task = audio_service.get_task(task_id)
            self.send_json({
                "success": True,
                "task_id": task_id,
                "task": task,
                "message": "Audio merge task started in background"
            })
        except Exception as e:
            self.send_error_json(str(e), status=HTTPStatus.BAD_REQUEST)


# ----------------------------------------------------------------------
# Multi-threaded HTTP Server
# ----------------------------------------------------------------------
class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def print_banner(port, interfaces):
    rec_ip = "127.0.0.1"
    for desc, ip, is_wifi in interfaces:
        if is_wifi and not ip.startswith("127."):
            rec_ip = ip
            break
    if rec_ip == "127.0.0.1":
        for desc, ip, is_wifi in interfaces:
            if not ip.startswith("127."):
                rec_ip = ip
                break

    car_url = f"http://{rec_ip}:{port}/"
    admin_url = f"http://{rec_ip}:{port}/admin"
    studio_url = f"http://{rec_ip}:{port}/studio"
    local_admin_url = f"http://localhost:{port}/admin"
    local_studio_url = f"http://localhost:{port}/studio"

    ffmpeg_status = "Available (Ready)" if audio_service.is_available() else "NOT FOUND (Install via 'brew install ffmpeg')"

    border = "=" * 66
    print(border)
    print("   LOCAL MUSIC DROP SERVER & AUDIO STUDIO (macOS & Car)")
    print(border)
    print(f" * Status         : Running")
    print(f" * Port           : {port}")
    print(f" * FFmpeg Engine  : {ffmpeg_status}")
    print(f" * Music Folder   : {MUSIC_DIR}")
    print()
    print(" [Access URLs]")
    print(f" -> Android Car Screen : {car_url}")
    print(f" -> Audio Studio (Mac) : {studio_url}")
    print(f"                         {local_studio_url}")
    print(f" -> Mac Upload/Admin   : {admin_url}")
    print(f"                         {local_admin_url}")
    print()
    print(" [Detected Network Interfaces]")
    for desc, ip, is_wifi in interfaces:
        mark = " <-- [RECOMMENDED FOR CAR HOTSPOT]" if ip == rec_ip and ip != "127.0.0.1" else ""
        print(f"   * {desc.ljust(18)}: {ip}{mark}")
    print()
    print(" [Quick Instructions]")
    print(" 1. Connect Mac and Android Head Unit to the same Wi-Fi Hotspot.")
    print(f" 2. On Mac: Manage songs at '{local_admin_url}', merge at '{local_studio_url}'.")
    print(f" 3. On Car: Open Chrome and visit '{car_url}'.")
    print(" 4. Tap the large [DOWNLOAD] button next to any song.")
    print()
    print(" [Security Notice]")
    print(" ! This server is designed strictly for private Local Hotspot use.")
    print(" ! DO NOT expose port 8000 or this server to the public Internet.")
    print(border)
    sys.stdout.flush()


def run_server(port=DEFAULT_PORT):
    interfaces = get_network_interfaces()
    server_address = ("0.0.0.0", port)

    try:
        httpd = ThreadedHTTPServer(server_address, LocalMusicRequestHandler)
    except OSError as e:
        print(f"\n[Error] Could not bind to port {port}: {e}")
        print("Tip: Port may be in use by another application. Try another port or terminate existing process.")
        sys.exit(1)

    print_banner(port, interfaces)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[Shutting Down] Local Music Server stopped cleanly.")
        httpd.server_close()
        sys.exit(0)


if __name__ == "__main__":
    port = DEFAULT_PORT
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Invalid port '{sys.argv[1]}'. Using default {DEFAULT_PORT}.")
    run_server(port)
