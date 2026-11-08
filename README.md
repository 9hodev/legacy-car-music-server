# Local Music Drop Server, Audio Studio & Network Dashboard 🎵🚗🎛️📊

> **A zero-dependency HTTP Music Server, Audio Studio & Network Dashboard for macOS & older Android Head Units over Wi-Fi Hotspot.**
> ส่งไฟล์เพลง ประมวลผลเสียง (Convert, Optimize, Merge, Crossfade) และตรวจสอบเครือข่าย/อุปกรณ์ (Device Registry, Live Throughput, Activity Logs) จาก Mac ไปยังจอรถยนต์ Android รุ่นเก่าผ่าน Wi-Fi Hotspot

---

## 📌 สรุปคุณสมบัติใหม่: Network Dashboard & Device Monitoring

1. **Network Dashboard (`/dashboard`):**
   - **Network Overview:** แสดงสถานะเซิร์ฟเวอร์, IP & Port, Server Uptime, จำนวนอุปกรณ์ Online/Offline, จำนวน Active Connections, จำนวน Active File Transfers (แยก Upload/Download), สปีด Throughput แบบเรียลไทม์ และปริมาณข้อมูลรวมที่รับ-ส่ง
   - **Live Transfers:** ติดตามความคืบหน้าการส่งไฟล์ (Progress %, Transfer Speed, ETA) โดยไม่นับรวม Background Polling หรือ Heartbeat
   - **Server Controls:** คัดลอก URL เซิร์ฟเวอร์, จัดการเซสชัน Admin, และสั่งปิดเซิร์ฟเวอร์อย่างปลอดภัย (Graceful Shutdown)
2. **Device Discovery & Registry:**
   - **Persistent Device ID:** สร้างและจดจำ Device ID เฉพาะสำหรับแต่ละอุปกรณ์ (เก็บใน `localStorage` หรือส่งผ่าน Header)
   - **Client Heartbeat Mechanism:** ส่งสัญญาณ Heartbeat ทุก 10–15 วินาที หากไม่มีสัญญาณเกิน 35–45 วินาที ระบบจะเปลี่ยนสถานะเป็น Offline อัตโนมัติในฐานข้อมูล
   - **Device Type & Activity:** แยกประเภทอุปกรณ์ (Desktop, Mobile, Car Head Unit) และแสดงกิจกรรมปัจจุบัน (Idle, Uploading, Downloading, Playing Audio)
   - **Device Revocation:** แอดมินสามารถเพิกถอน (Revoke) การเข้าถึงของอุปกรณ์ที่ไม่พึงประสงค์ได้
3. **SQLite Activity & Security Logging (`music_server.db`):**
   - ฐานข้อมูล SQLite ในโหมด Write-Ahead Logging (WAL) เพื่อรองรับการทำงานพร้อมกันหลายเธรด
   - บันทึกประวัติ: Server Started/Stopped, Device Registered, Device Online/Offline, Upload/Download, File Renamed/Deleted, Audio Convert/Merge, และ Auth Success/Failed
   - **Log Filtering & Pagination:** ค้นหาตามชื่อไฟล์, IP, อุปกรณ์, หรือกรองตามประเภทเหตุการณ์ (Event Type) พร้อมระบบแบ่งหน้า (Pagination)
   - **Export CSV:** ดาวน์โหลดบันทึกทั้งหมดเป็นไฟล์ CSV ได้ทันที
   - ข้อมูลบันทึกและรายการอุปกรณ์คงอยู่ถาวรแม้ปิดเปิดเซิร์ฟเวอร์ใหม่ (Survives Server Restarts)
4. **Device Security & Admin Authentication:**
   - ระบบล็อกอิน Admin ด้วย PIN หรือ Password ที่กำหนดค่าได้อย่างง่ายดายและปลอดภัยผ่าน `config.json` (หรือ Environment Variables: `ADMIN_PIN`, `ADMIN_PASSWORD`)
   - **Safe for Public GitHub:** ไฟล์ `config.json` ที่เก็บรหัสผ่านจริงถูกระบุไว้ใน `.gitignore` จึงไม่มีการรั่วไหลขึ้น GitHub แน่นอน โดยมี `config.example.json` เป็นแม่แบบให้ใช้งาน
   - **Dashboard Lock Screen:** หน้า `/dashboard` ถูกล็อกไว้ด้วยหน้าต่างยืนยันตัวตน Admin โดยอัตโนมัติ จะไม่แสดงข้อมูลเครือข่าย อุปกรณ์ หรือประวัติ Log จนกว่าจะกรอกรหัสผ่านถูกต้อง
   - รหัสผ่านถูกเข้ารหัสด้วย PBKDF2-HMAC-SHA256 (100,000 rounds) ร่วมกับ Salt แบบสุ่ม
   - เปรียบเทียบรหัสผ่านและโทเค็นด้วย Constant-time comparison (`hmac.compare_digest`) ป้องกัน Timing Attacks
   - **Rate Limiting:** จำกัดการล็อกอินผิดพลาดสูงสุด 5 ครั้งต่อ 5 นาที หากเกินจะบล็อก IP นั้นเป็นเวลา 60 วินาที
   - ไม่บันทึกรหัสผ่านหรือโทเค็นเป็น Plaintext ใน Log หรือหน้าเว็บเด็ดขาด
5. **รักษาความเข้ากันได้ 100% กับจอรถยนต์ Android รุ่นเก่า (Android 4.4 – 8.0):**
   - หน้าจอรถยนต์ (`/`) และการดาวน์โหลด (`/download/...`) เข้าถึงได้โดยตรง ไม่ต้องล็อกอิน ไม่ต้องใช้ JavaScript
   - รองรับการ Resume การดาวน์โหลดผ่าน HTTP Range Header

---

## ⚠️ ข้อจำกัดสำคัญของระบบเครือข่าย (Important Network Limitations)

> 💡 **โปรดทราบข้อจำกัดทางเทคนิคของเครือข่าย Wi-Fi และ HTTP:**
> 1. **A normal HTTP server cannot enumerate every device connected to the same Wi-Fi network:** HTTP Server ปกติไม่สามารถสแกนหรือตรวจจับทุกอุปกรณ์ที่เกาะอยู่ใน Wi-Fi เดียวกันได้โดยที่อุปกรณ์นั้นไม่ได้ส่ง Request เข้ามายังเซิร์ฟเวอร์
> 2. **Device discovery requires explicit client registration or LAN communication:** การระบุตัวตนของอุปกรณ์ (Device Registry) ต้องอาศัยการส่งสัญญาณลงทะเบียนจากฝั่ง Client ผ่าน Browser หรือแอปพลิเคชัน
> 3. **Hotspot client isolation may prevent device-to-device communication:** โหมด Hotspot บนมือถือหรือ Router บางรุ่นอาจเปิดฟีเจอร์ "AP/Client Isolation" ซึ่งจะบล็อกไม่ให้อุปกรณ์สองเครื่องคุยกันโดยตรง (หากพบปัญหาจอรถมองไม่เห็น Mac ให้ตรวจสอบการตั้งค่า Hotspot)
> 4. **A device can appear offline because it is sleeping or temporarily disconnected:** อุปกรณ์อาจถูกระบุว่า "Offline" หากหน้าจอดับ เข้าสู่โหมด Sleep หรือสัญญาณ Wi-Fi หลุดชั่วคราว
> 5. **An HTTP connection does not necessarily represent a persistent online device:** การเชื่อมต่อ HTTP เป็นแบบ Request-Response (Stateless) การที่ Socket เปิดหรือปิดไม่ได้หมายความว่าอุปกรณ์นั้นเปิดหรือปิดอยู่ตลอดเวลา ระบบจึงใช้ Heartbeat และ `last_seen` ในการประเมินสถานะออนไลน์

---

## 🔧 การติดตั้ง FFmpeg (สำหรับ Audio Studio)

ระบบประมวลผลเสียงใช้ FFmpeg ติดตั้งได้ง่ายๆ:
- **macOS:** `brew install ffmpeg`
- **Windows:** `winget install Gyan.FFmpeg`
- **Linux:** `sudo apt install -y ffmpeg`

---

## 🚀 วิธีเริ่มต้นใช้งาน (Quick Start)

รันเซิร์ฟเวอร์ด้วยคำสั่งเดียว:

```bash
python3 server.py
```

หน้าจอ Terminal จะแสดงข้อมูลการเข้าถึงทุกส่วน:

```text
====================================================================
   LOCAL MUSIC SERVER, AUDIO STUDIO & NETWORK DASHBOARD
====================================================================
 * Status         : Running
 * Port           : 8000
 * Database       : SQLite (music_server.db in WAL mode)
 * FFmpeg Engine  : Available (Ready)
 * Music Folder   : /Users/.../music

 [Access URLs]
 -> Android Car Screen : http://192.168.43.50:8000/
 -> Network Dashboard  : http://192.168.43.50:8000/dashboard
                         http://localhost:8000/dashboard
 -> Audio Studio (Mac) : http://192.168.43.50:8000/studio
 -> Music Admin / DL   : http://192.168.43.50:8000/admin
====================================================================
```

---

## 📡 สรุป API Endpoints

### 1. หน้าเว็บ (Pages)
- `GET /` หรือ `/index.html`: Car Download Page (Zero-JS ready)
- `GET /dashboard`: Network Dashboard & Device Monitoring
- `GET /admin`: Music Upload & File Management
- `GET /studio`: Audio Merge & Crossfade Studio

### 2. แดชบอร์ดและอุปกรณ์ (Dashboard & Devices)
- `GET /api/dashboard/stats`: ข้อมูลสถิติเซิร์ฟเวอร์, Uptime, Throughput, และ Live Transfers
- `GET /api/devices`: รายการอุปกรณ์ที่ลงทะเบียนและประวัติการเชื่อมต่อ
- `POST /api/devices/register`: ลงทะเบียนอุปกรณ์ (`{"device_id": "...", "name": "...", "device_type": "..."}`)
- `POST /api/devices/heartbeat`: อัปเดตสถานะออนไลน์ (`{"device_id": "...", "current_activity": "..."}`)
- `POST /api/devices/revoke`: เพิกถอนสิทธิ์อุปกรณ์ (ต้องใช้ Admin Auth)

### 3. บันทึกประวัติ (Logs & Security)
- `GET /api/logs`: ดึงรายการ Log แบบแบ่งหน้าพร้อมตัวกรอง (`?page=1&limit=20&search=...&event_type=...`)
- `GET /api/logs/export`: ส่งออก Log เป็นไฟล์ `.csv`
- `POST /api/logs/clear`: ล้างประวัติ Log ทั้งหมด (ต้องใช้ Admin Auth)
- `POST /api/auth/login`: ตรวจสอบ PIN/Password (`{"secret": "your_pin_or_password"}`) รับ Session Token
- `POST /api/auth/logout`: ออกจากระบบเซสชันแอดมิน
- `GET /api/auth/status`: ตรวจสอบสถานะการยืนยันตัวตนในปัจจุบัน

### 4. การจัดการไฟล์และแปลงเสียง (Files & Audio Processing)
- `GET /api/files`: รายการไฟล์เสียง JSON (`?meta=1` เพื่อดูความยาว)
- `GET /download/<filename>`: สตรีมมิ่งดาวน์โหลดไฟล์เสียง Chunked 64KB
- `POST /api/upload`: อัปโหลดไฟล์เสียงสตรีมมิ่ง (รองรับ 100MB+)
- `POST /api/rename`: เปลี่ยนชื่อไฟล์โดยคงนามสกุลเดิม
- `POST /api/convert`: สั่งแปลงไฟล์หรือบีบอัดเสียงใน Background
- `POST /api/merge`: สั่งรวมไฟล์เสียงหลากฟอร์แมต (Concat, Silence, Crossfade)
- `POST /api/delete`: ลบไฟล์เสียงเดี่ยว (`{"filename": "..."}`) หรือลบแบบเลือกหลายไฟล์พร้อมกัน Batch Delete (`{"filenames": ["...", "..."]}`)
- `GET /api/tasks/<task_id>`: ติดตามความคืบหน้าของงานแปลง/รวมเสียง

---

## 📁 โครงสร้างโปรเจกต์ (Project Structure)

โปรเจกต์ได้รับการจัดระเบียบตามมาตรฐาน Clean Architecture แยกเป็นโมดูลชัดเจน:

```text
LocalShare/
├── server.py                   # Main HTTP Server Entry Point (Zero-dependency)
├── run_tests.py                # Master Automated Test Runner (All suites)
├── README.md                   # Project Documentation
├── requirements.txt            # Python Dependencies
├── .gitignore                  # Git Ignore configuration
│
├── src/                        # Backend Modules & Core Services
│   ├── __init__.py
│   ├── audio_service.py        # Audio Processing Coordinator & Task Queue
│   ├── audio_convert.py        # FFmpeg Audio Conversion & Optimization Engine
│   ├── audio_merge.py          # FFmpeg Audio Concatenation & Crossfade Engine
│   ├── auth_service.py         # PBKDF2 Auth, Constant-Time Compare & Rate Limiting
│   ├── db_service.py           # SQLite Database Manager (WAL mode & schema)
│   └── monitor_service.py      # Network Metrics, Device Registry & Activity Tracker
│
├── web/                        # Frontend UI Templates & Static Assets
│   ├── index.html              # Legacy Android Car Download Page (Zero-JS compatible)
│   ├── admin.html              # Music Upload & File Management Page
│   ├── studio.html             # Audio Merge & Crossfade Studio Page
│   ├── dashboard.html          # Network Dashboard & Device Monitoring Page
│   ├── css/
│   │   └── style.css           # Global Dark Theme Stylesheet
│   └── js/
│       ├── app.js              # Admin & Upload Logic (Streaming Chunked Upload)
│       ├── studio.js           # Audio Studio Logic (Drag & Drop track ordering)
│       └── dashboard.js        # Network Dashboard Real-time Polling & Log UI
│
├── data/                       # Persistent Data Storage
│   └── music_server.db         # SQLite Database (survives restarts)
│
├── music/                      # Music Files Repository (Uploaded & converted audio)
│
└── tests/                      # Automated Test Suites
    ├── __init__.py
    ├── test_integration.py     # Base HTTP Server & Streaming Upload/Download Tests
    ├── test_audio_studio.py    # FFmpeg Convert & Merge Studio Tests (10 tests)
    └── test_dashboard_monitoring.py # Network Dashboard & Device Monitoring Tests (11 tests)
```

---

## 🧪 การทดสอบระบบ (Automated Tests)

คุณสามารถรันการทดสอบทั้งหมดผ่าน **Master Test Runner** คำสั่งเดียว:

```bash
python run_tests.py
```

หรือเลือกรันเฉพาะชุดทดสอบที่ต้องการ:

1. **ชุดทดสอบแดชบอร์ดและเครือข่าย (11 การทดสอบ):**
   ```bash
   python tests/test_dashboard_monitoring.py
   ```
   *(ทดสอบการเชื่อมต่อพร้อมกัน, Device Heartbeat, Offline Timeout, Log บันทึก Upload/Download, Interrupted Transfer, Server Restart Persistence, Auth Rate Limiting, และความเข้ากันได้กับจอรถ)*

2. **ชุดทดสอบการประมวลผลเสียง FFmpeg (10 การทดสอบ):**
   ```bash
   python tests/test_audio_studio.py
   ```

3. **ชุดทดสอบ Integration พื้นฐาน:**
   ```bash
   python tests/test_integration.py
   ```
