# Local Music Drop Server, Audio Studio & Network Dashboard 🎵🚗🎛️📊

> **A zero-dependency local HTTP music server, audio processing studio, and network monitoring dashboard designed for older Android car head units over an offline Wi-Fi hotspot.**

---

## 💡 The Story: Why This Project Exists

Modern file-sharing tools assume modern devices with fast processors, gigabytes of RAM, and cloud internet access. However, millions of vehicles still run **older aftermarket Android head units** (Android 4.4 KitKat through Android 8.0 Oreo) that suffer from severe real-world limitations:

1. **No Accessible USB Port:** 
   In many car installations, USB cables are routed behind the dashboard, broken, only support 0.5A charging, or are dedicated exclusively to a reverse camera or proprietary dashcam.
2. **Extremely Constrained Hardware:**
   Older head units typically have 512 MB to 1 GB of RAM and weak quad-core processors. Heavy file-sharing apps (AirDroid, Send Anywhere, Google Drive, Telegram, Nextcloud) crash, fail to install, or cause the head unit to freeze while driving.
3. **No Google Play Services (GMS):**
   Most car infotainment systems run stripped-down Android ROMs where Google Play Store does not work, and sideloading modern APKs fails due to incompatible API levels.
4. **Offline / No Internet Connection:**
   In a moving vehicle, internet connectivity is often limited to a portable phone hotspot or may have no cellular service at all.

### 🎯 The Solution

**Local Music Drop Server** turns your Mac, PC, or laptop into a lightweight, local web server operating completely offline over your vehicle's Wi-Fi hotspot:

- **Zero App Installation:** The car head unit needs **NO** app installed. Just open the built-in Android browser or Chrome and navigate to `http://<LAPTOP_IP>:8000/`.
- **Zero JavaScript on the Car Screen:** The car download page is rendered in **100% pure semantic HTML5**. It works flawlessly on obsolete browsers from 2013 without crashing or executing client-side scripts.
- **Heavy Lifting Stays on the Laptop:** All heavy computations—converting incompatible formats (FLAC/OGG/WAV to MP3), reducing bitrates to save the car's limited internal flash storage, and merging multiple tracks—happen on your computer via background FFmpeg workers, not on the car head unit.
- **Resumable Chunked Downloads:** HTTP Range header support allows large downloads to be paused and resumed seamlessly without losing progress.

---

## ✨ Features Overview

### 1. 🚗 Zero-JS Car Download Portal (`/`)
- Pure HTML5 download portal engineered specifically for legacy Android Chrome and Android Stock Browsers.
- One-tap direct downloads with standard browser download management.
- Supports HTTP Range Requests (`bytes=start-end`) for resumable downloads.
- Clean high-contrast, touch-friendly UI designed for in-car dashboard screens.

### 2. ⚡ Zero-Dependency Core Server
- Built exclusively with Python 3 Standard Library modules (`http.server`, `socketserver`, `sqlite3`, `hashlib`, `hmac`, `secrets`, `threading`, `subprocess`).
- Streaming multipart parser reads 100MB+ files in small 64KB chunks directly to disk—never buffering entire files in memory.
- Cross-platform launcher scripts: [start.sh](file:///d:/MyPrograms/Project/LocalShare/start.sh) for macOS/Linux and [start.bat](file:///d:/MyPrograms/Project/LocalShare/start.bat) for Windows.

### 3. 📁 File Management & Multi-Select Batch Delete (`/admin`)
- Drag-and-drop upload zone with real-time speed, progress bar, and percentage indicators.
- **Multi-Select Batch Delete:** Check individual songs or use "Select All" with a batch action toolbar to delete multiple tracks in a single confirmation.
- **Safe Rename:** Rename songs without losing original extensions; protects against path traversal and duplicate names.
- **Full Unicode & Thai Support:** Native UTF-8 parsing with RFC 5987 / RFC 6266 (`filename*=UTF-8''...`) support and automated mojibake recovery (e.g. recovering corrupted Latin-1 byte sequences).

### 4. 🎛️ Audio Studio & FFmpeg Engine (`/studio`)
- **Audio Optimization & Conversion:** Convert between MP3, WAV, M4A, AAC, FLAC, OGG, and OPUS with customizable bitrates (96–320 kbps) and sample rates (44.1 / 48 kHz).
- **Mixed Format Concatenation:** Seamlessly merge different input formats (e.g., MP3 + WAV + M4A) with auto-normalization.
- **Crossfade & Silence Gaps:** Insert custom silence pauses between tracks or blend tracks using multi-channel audio crossfading.
- **Background Task Queue:** Audio jobs run asynchronously in background worker threads without blocking file transfers or downloads.

### 5. 📊 Network Dashboard & Device Monitoring (`/dashboard`)
- **Real-Time Network Metrics:** Server uptime, active TCP connections, live upload/download throughput (KB/s, MB/s), and total transfer volume.
- **Live Transfer Tracker:** Dedicated progress and ETA tracking for active file transfers (background polling excluded).
- **Device Discovery & Registry:** Persistent Device IDs, client heartbeat mechanism (10–15s ping, 35–45s offline timeout), and device classification (Desktop, Mobile, Car Head Unit).
- **Device Revocation:** Admins can instantly revoke unwanted client access.

### 6. 🔒 SQLite Activity Logging & Admin Security
- **Persistent Database:** SQLite in Write-Ahead Logging (WAL) mode for multi-threaded concurrency.
- **Comprehensive Event Logs:** Records server starts/stops, device heartbeats, uploads, downloads, conversions, renames, and auth failures.
- **Search, Filter & CSV Export:** Search logs by keyword, filter by event type, paginate records, and export to CSV.
- **Dashboard Lock Screen:** `/dashboard` is gated behind an authentication screen—no metrics or logs are visible to unauthorized clients.
- **Safe for Public GitHub:** Admin PIN and password are configured in `config.json` (gitignored). A `config.example.json` template is provided for convenience.
- **Security Protections:** PBKDF2-HMAC-SHA256 password hashing (100,000 iterations), random salt, constant-time comparisons (`hmac.compare_digest`), and IP-based rate limiting (5 failed attempts per 5 minutes triggers lockout).

---

## 🔧 Prerequisites

- **Python 3.8+** (Uses standard library only, no `pip install` required).
- **FFmpeg** (Required only for Audio Studio conversion and merging):
  - **macOS:** `brew install ffmpeg`
  - **Windows:** `winget install Gyan.FFmpeg`
  - **Linux:** `sudo apt update && sudo apt install -y ffmpeg`

---

## 🚀 Quick Start

### 1. Launch the Server

Run with a single command:

```bash
# macOS / Linux
./start.sh
# or: python3 server.py

# Windows
start.bat
# or: python server.py
```

### 2. Connect Your Car Head Unit

1. Enable the **Personal Hotspot** on your phone or laptop.
2. Connect both your laptop and the car's Android head unit to the **same Wi-Fi hotspot**.
3. Check the startup banner in your laptop terminal:

```text
====================================================================
   LOCAL MUSIC SERVER, AUDIO STUDIO & NETWORK DASHBOARD
====================================================================
 * Status         : Running
 * Port           : 8000
 * Database       : SQLite (data/music_server.db in WAL mode)
 * FFmpeg Engine  : Available (Ready)
 * Music Folder   : /Users/.../music

 [Access URLs]
 -> Android Car Screen : http://192.168.43.50:8000/
 -> Network Dashboard  : http://192.168.43.50:8000/dashboard
                         http://localhost:8000/dashboard
 -> Audio Studio (Mac) : http://192.168.43.50:8000/studio
 -> Music Admin / DL   : http://192.168.43.50:8000/admin

 [Security & Access Notice]
 - Admin Auth         : Protected (Credentials configured in config.json)
 - Car View ('/')     : 100% Zero-JS and requires no authentication.
 - Wi-Fi Hotspot only : DO NOT expose this port to the public internet.
====================================================================
```

4. On your **Car Head Unit**, open the browser and visit `http://192.168.43.50:8000/`. Tap **DOWNLOAD** next to any song.

---

## ⚙️ Configuration (`config.json`)

On the first run, the server automatically generates `config.json` in the root directory. This file is **ignored by Git** to prevent leaking passwords to public repositories:

```json
{
  "server_port": 8000,
  "admin_pin": "8888",
  "admin_password": "admin"
}
```

You can change `admin_pin` and `admin_password` to your desired values anytime. Restarting the server will automatically update the hashed credentials in the SQLite database.

### Environment Variable Overrides
You can also override settings via environment variables:
- `ADMIN_PIN`: Custom admin PIN
- `ADMIN_PASSWORD`: Custom admin password
- `LOCAL_MUSIC_PORT`: Custom port number

---

## 📁 Project Structure

The project follows a clean modular architecture:

```text
LocalShare/
├── server.py                        # HTTP Server Entry Point (Standard Library only)
├── run_tests.py                     # Master Automated Test Runner (All suites)
├── start.sh                         # Unix/macOS Launcher Script (Executable 100755)
├── start.bat                        # Windows Launcher Script
├── config.example.json              # Public Template Configuration
├── README.md                        # Documentation
├── requirements.txt                 # Documentation of standard library modules
├── .gitignore                       # Git Ignore configuration
│
├── src/                             # Backend Services & Logic
│   ├── __init__.py
│   ├── audio_service.py             # Task coordinator & background worker queue
│   ├── audio_convert.py             # FFmpeg conversion and optimization engine
│   ├── audio_merge.py               # FFmpeg concatenation, silence & crossfade engine
│   ├── auth_service.py              # PBKDF2 hashing, constant-time compare & rate limiter
│   ├── db_service.py                # SQLite database management (WAL mode)
│   └── monitor_service.py           # Metrics tracker, device registry & activity logger
│
├── web/                             # Frontend UI & Assets
│   ├── index.html                   # Zero-JS Legacy Car Download Portal
│   ├── admin.html                   # Upload, batch delete & song management
│   ├── studio.html                  # Audio Studio merge & crossfade interface
│   ├── dashboard.html               # Network Dashboard & Device Monitoring view
│   ├── css/
│   │   └── style.css                # Global responsive dark theme stylesheet
│   └── js/
│       ├── app.js                   # Admin client logic (Streaming upload & batch delete)
│       ├── studio.js                # Studio client logic (Drag & drop track ordering)
│       └── dashboard.js             # Dashboard client logic (Lock screen & metrics polling)
│
├── data/                            # Persistent Data Storage (Gitignored)
│   ├── .gitkeep
│   └── music_server.db              # SQLite Database
│
├── music/                           # Music Storage Repository (Gitignored)
│   └── .gitkeep
│
└── tests/                           # Automated Test Suites
    ├── __init__.py
    ├── test_integration.py          # HTTP streaming, Thai Unicode, 100MB+, batch delete
    ├── test_audio_studio.py         # FFmpeg conversion, crossfade & merge tests (10 tests)
    └── test_dashboard_monitoring.py # Concurrency, heartbeat, auth, logging tests (11 tests)
```

---

## 📡 API Reference

### 1. Web Pages
- `GET /` or `/index.html`: Zero-JS Car Download Portal
- `GET /admin`: File Upload and Management Console
- `GET /studio`: Audio Merge and Crossfade Studio
- `GET /dashboard`: Network Dashboard & Monitoring (Gated behind Lock Screen)

### 2. Files & Audio Operations
- `GET /api/files`: JSON list of all songs (`?meta=1` includes bitrate, duration, sample rate)
- `GET /download/<filename>`: Stream download file with HTTP Range support
- `POST /api/upload`: Streaming chunked multipart upload (supports 100MB+ files)
- `POST /api/rename`: Rename audio file while strictly preserving original format
- `POST /api/delete`: Delete single file (`{"filename": "..."}`) or batch delete (`{"filenames": ["...", "..."]}`)
- `POST /api/convert`: Launch background audio conversion / bitrate optimization
- `POST /api/merge`: Launch background multi-track concatenation with crossfade
- `GET /api/tasks/<task_id>`: Check audio conversion or merge progress

### 3. Monitoring & Device Registry
- `GET /api/dashboard/stats`: Server health, uptime, throughput, active connections, and live transfers
- `GET /api/devices`: List registered devices and online/offline status (Requires Admin Auth)
- `POST /api/devices/register`: Register client device (`device_id`, `name`, `device_type`)
- `POST /api/devices/heartbeat`: Update device online status (`device_id`, `current_activity`)
- `POST /api/devices/revoke`: Revoke device access (Requires Admin Auth)

### 4. Security & Logs
- `POST /api/auth/login`: Authenticate with PIN or Password (`{"secret": "..."}`)
- `POST /api/auth/logout`: Revoke active admin session token
- `GET /api/auth/status`: Check current session authentication status
- `GET /api/logs`: Paginated activity logs with search and filtering (Requires Admin Auth)
- `GET /api/logs/export`: Download all activity logs as `.csv` (Requires Admin Auth)
- `POST /api/logs/clear`: Clear activity log history and vacuum database (Requires Admin Auth)
- `POST /api/server/stop`: Graceful server shutdown (Requires Admin Auth)

---

## 🧪 Automated Testing

Run the complete test suite with the master test runner:

```bash
python run_tests.py
```

Or run individual suites:

```bash
# 1. Base HTTP & Streaming Integration Tests
python tests/test_integration.py

# 2. FFmpeg Audio Studio Conversion & Merge Tests
python tests/test_audio_studio.py

# 3. Network Dashboard, Heartbeat & Security Tests
python tests/test_dashboard_monitoring.py
```

---

## ⚠️ Important Network Notes

1. **AP / Client Isolation:** Some phone hotspots and travel routers have "AP Isolation" or "Client Isolation" turned on by default. If your car head unit cannot open the URL, disable AP Isolation in your hotspot settings so connected devices can talk to each other.
2. **Device Discovery:** Normal HTTP servers cannot blindly probe all devices connected to a Wi-Fi hotspot without an explicit request. The server identifies devices when they send a registration request or access the server.
3. **Hotspot IP Changes:** When toggling a phone hotspot, your laptop's Wi-Fi IP address may change. Always refer to the startup banner in the terminal for the latest URL.

---

## 📄 License

MIT License. Open-source and free for personal and vehicle use.
