# Local Music Drop Server 🎵🚗

> **A zero-dependency Local HTTP Music Server for macOS & older Android Head Units over Wi-Fi Hotspot.**
> ส่งไฟล์เพลงจาก Mac ไปยังจอรถยนต์ Android รุ่นเก่าผ่าน Wi-Fi Hotspot โดยไม่ต้องต่อเน็ต ไม่ต้องผ่าน Cloud และไม่ต้องลง Library เพิ่มเติม

---

## 📌 จุดเด่นและคุณสมบัติหลัก (Key Features)

- **Pure Python 3 Standard Library:** ไม่ต้องติดตั้งแพ็กเกจภายนอกจาก `pip` (`0 External Dependencies`)
- **Streaming Upload & Download:** อ่านและเขียนข้อมูลแบบ Streaming ด้วย Buffer ขนาด 64 KB รองรับไฟล์ขนาดใหญ่ **100 MB หรือมากกว่า** โดยไม่โหลดทั้งไฟล์เข้า RAM และไม่ทำให้ Server ค้าง
- **Multi-threaded Architecture:** รองรับการเชื่อมต่อหลายอุปกรณ์พร้อมกัน ไม่บล็อกระหว่างการอัปโหลดหรือดาวน์โหลด
- **ออกแบบพิเศษสำหรับจอรถยนต์ Android รุ่นเก่า (Android 4.4 - 8.0):**
  - แสดงผลรายการเพลงและลิงก์ดาวน์โหลดแบบ **Zero-JS (Server-rendered direct `<a href="...">` anchors)** สามารถกดดาวน์โหลดได้ทันทีแม้จอรถจะไม่รองรับ JavaScript ยุคใหม่
  - ดีไซน์ Dark Theme คอนทราสต์สูง ปุ่มขนาดใหญ่พิเศษ (Touch Target 56px+) อ่านง่ายและกดง่ายบนจอสัมผัสในรถยนต์
  - ปราศจาก External CDN, CSS Framework หรือ HTTPS ที่มักติดปัญหา SSL Certificate บนระบบรุ่นเก่า
  - รองรับ HTTP Range Requests (`bytes=start-end`) สำหรับการดาวน์โหลดต่อ (Resume) หรือเล่นเพลง
- **Mac Admin Dashboard:**
  - ลากและวางไฟล์ (Drag & Drop Zone ขนาดใหญ่)
  - แสดงชื่อไฟล์, ขนาดไฟล์, และ Progress Bar แบบเรียลไทม์ผ่าน `XMLHttpRequest.upload.onprogress` พร้อมบอกความเร็วในการอัปโหลด
  - ปุ่ม **Copy Download URL** (พร้อม Fallback สำหรับเครือข่าย Local HTTP) และปุ่ม **Delete** ไฟล์
  - ระบบค้นหาและตัวกรองเพลง
- **ความปลอดภัย (Security by Design):**
  - ตรวจสอบ Path Traversal ป้องกันการเข้าถึงไฟล์นอกโฟลเดอร์ `music/`
  - อนุญาตเฉพาะนามสกุลไฟล์เสียง: `.mp3`, `.m4a`, `.aac`, `.flac`, `.wav`, `.ogg`
  - ป้องกันชื่อไฟล์ชนกันโดยเติม `(1)`, `(2)` อัตโนมัติ และกำจัดอักขระพิเศษอันตราย

---

## 🗂 โครงสร้างโปรเจกต์ (Project Structure)

```text
LocalShare/
├── server.py               # Backend: Multi-threaded HTTP Server + Streaming Parser
├── index.html              # Frontend: Car Download Page (Direct Anchors, Zero-JS ready)
├── admin.html              # Frontend: Mac Admin Page (Drag & Drop, Progress Bar, Manage)
├── style.css               # Shared CSS (Dark automotive theme + Mac Admin styles)
├── app.js                  # Admin Frontend JS (Vanilla JS, XMLHttpRequest, No dependencies)
├── requirements.txt        # เอกสารระบุว่าไม่ต้องติดตั้ง Third-party library
├── run_integration_test.py # ชุดทดสอบอัตโนมัติ (GET, 100MB Upload, Download, Range, Security)
└── music/                  # โฟลเดอร์เก็บไฟล์เพลง (สร้างอัตโนมัติเมื่อเปิดเซิร์ฟเวอร์)
```

---

## 🚀 วิธีเริ่มต้นใช้งาน (Quick Start)

### 1. รัน Server บน Mac

เปิด Terminal บน macOS แล้วใช้คำสั่งเดียว:

```bash
python3 server.py
```

*(หรือกำหนด Port อื่นตามต้องการ เช่น `python3 server.py 8080`)*

เมื่อ Server เริ่มทำงาน ระบบจะตรวจจับ Network Interface (เช่น `en0` Wi-Fi) และแสดง Banner ดังนี้:

```text
================================================================
   LOCAL MUSIC DROP SERVER (macOS & Android Head Unit)
================================================================
 * Status         : Running
 * Port           : 8000
 * Music Folder   : /Users/.../music

 [Access URLs]
 -> Android Car Screen : http://192.168.43.50:8000/
 -> Mac Upload/Admin   : http://192.168.43.50:8000/admin
                         http://localhost:8000/admin

 [Detected Network Interfaces]
   * Wi-Fi (en0)       : 192.168.43.50 <-- [RECOMMENDED FOR CAR HOTSPOT]
   * Localhost         : 127.0.0.1

 [Quick Instructions]
 1. Connect Mac and Android Head Unit to the same Wi-Fi Hotspot.
 2. On Mac: Open 'http://localhost:8000/admin' and drag & drop music files.
 3. On Car: Open Chrome and visit 'http://192.168.43.50:8000/'.
 4. Tap the large [DOWNLOAD] button next to any song.

 [Security Notice]
 ! This server is designed strictly for private Local Hotspot use.
 ! DO NOT expose port 8000 or this server to the public Internet.
================================================================
```

---

## 🔄 ขั้นตอนการเชื่อมต่อในรถยนต์ (Workflow Guide)

```
+------------------+         Wi-Fi Hotspot (No Internet needed)         +----------------------+
|     MacBook      | <================================================> | Android Head Unit    |
| (Local Server)   |                                                    | (Chrome Browser)     |
|                  |                                                    |                      |
|  1. ลากไฟล์เพลงลง  |  2. เก็บใน music/   ==>  3. สตรีมผ่าน HTTP  ==>  |  4. กดปุ่ม DOWNLOAD  |
|     /admin       |                                                    |     บันทึกลงจอรถทันที  |
+------------------+                                                    +----------------------+
```

### รูปแบบการต่อ Hotspot ที่แนะนำ:
1. **ใช้ Hotspot จากมือถือ:**
   - เปิด Personal Hotspot จากมือถือ
   - นำ Mac และจอแอนดรอยด์ในรถต่อเข้า Wi-Fi Hotspot เดียวกัน
2. **ใช้ Hotspot จากตัวจอรถยนต์:**
   - ถ้าจอรถปล่อย Wi-Fi Hotspot ได้ ให้ Mac ต่อเข้า Wi-Fi ของจอรถ
3. **ใช้ Mac แชร์ Wi-Fi:**
   - ไปที่ Mac *System Settings > General > Sharing > Internet Sharing*

### ขั้นตอนการใช้งาน:
1. **บน Mac:** เปิด Browser ไปที่ `http://localhost:8000/admin`
   - ลากไฟล์เพลงหลายๆ ไฟล์มาวางในกรอบ **Drop Zone**
   - ดู Progress Bar แสดงผลแบบเรียลไทม์จนอัปโหลดสำเร็จ
2. **บนจอรถ Android:** เปิดแอป Chrome หรือ Browser ติดรถ
   - พิมพ์ URL ตามที่แสดงในคอนโซล Mac เช่น `http://192.168.43.50:8000/`
   - จะเห็นรายการเพลงที่อัปโหลดไว้ พร้อมขนาดไฟล์
   - แตะปุ่มสีเขียวขนาดใหญ่ **`[ DOWNLOAD ]`** ไฟล์จะถูกบันทึกลงในโฟลเดอร์ `Download` ของเครื่องเสียงรถยนต์ทันที

---

## 🛠 รายละเอียดทางเทคนิค (Technical Specifications)

### 1. Routing Table
| Method | Path | รายละเอียด |
| :--- | :--- | :--- |
| `GET` | `/` หรือ `/index.html` | Car Download Page (Server-rendered HTML list พร้อม Anchor Tags) |
| `GET` | `/admin` หรือ `/admin.html`| Admin Upload & Management Page |
| `GET` | `/style.css` | Stylesheet (รองรับทั้งจอรถยนต์คอนทราสต์สูง และ Mac Dashboard) |
| `GET` | `/app.js` | Admin Vanilla JavaScript (Progress Bar, Copy Link, Delete) |
| `GET` | `/api/files` | JSON ข้อมูลเพลงทั้งหมด (ชื่อ, ขนาดไฟล์, วันที่, URL ดาวน์โหลด) |
| `GET` | `/download/<filename>` | สตรีมมิ่งไฟล์เสียง Chunked 64KB พร้อม `Content-Disposition: attachment` |
| `POST`| `/api/upload` | สตรีมมิ่ง Multipart/form-data รับไฟล์ 100MB+ บันทึกลง Disk โดยตรง |
| `POST`| `/api/delete` | ลบไฟล์เสียงออกจากเซิร์ฟเวอร์อย่างปลอดภัย |

### 2. นามสกุลไฟล์เสียงที่รองรับ
- `.mp3` (`audio/mpeg`)
- `.m4a` (`audio/mp4`)
- `.aac` (`audio/aac`)
- `.flac` (`audio/flac`)
- `.wav` (`audio/wav`)
- `.ogg` (`audio/ogg`)

### 3. การประหยัดหน่วยความจำ (Streaming Parser)
Server ไม่ใช้ `cgi.FieldStorage` (ซึ่งถูก Deprecate และถอดออกใน Python 3.13) และไม่ใช้ `read(content_length)` แต่ใช้ Parser ที่ออกแบบขึ้นมาให้อ่านเป็น Chunk ทีละ 64 KB ตรวจจับ Boundary และเขียนลงไฟล์ชั่วคราว (`.tmp_*`) ในดิสก์ทันที ทำให้การอัปโหลดไฟล์ขนาดใหญ่ระดับ 100 MB - 1 GB ใช้หน่วยความจำ RAM คงที่เพียง ~64–128 KB เท่านั้น

---

## 🧪 การทดสอบระบบ (Automated Tests)

โปรเจกต์มีสคริปต์ทดสอบระบบอัตโนมัติ `run_integration_test.py` สามารถรันเพื่อตรวจสอบความถูกต้องได้ทันที:

```bash
python3 run_integration_test.py
```

**สิ่งที่สคริปต์ตรวจสอบ:**
- [x] ตรวจสอบหน้า Car (`/`) และหน้า Admin (`/admin`)
- [x] ตรวจสอบ Static Assets (`style.css`, `app.js`)
- [x] ตรวจสอบ API รายการไฟล์ (`/api/files`)
- [x] ทดสอบ Streaming Upload ไฟล์เสียง 1 MB
- [x] ทดสอบ **Streaming Upload ไฟล์ขนาดใหญ่ 100 MB** และเทียบขนาดบนดิสก์แบบไบต์ต่อไบต์
- [x] ทดสอบ Streaming Download พร้อม Header `Content-Disposition`
- [x] ทดสอบ **HTTP Range Request (Partial Content 206)**
- [x] ทดสอบความปลอดภัย: ปฏิเสธไฟล์นามสกุลอันตราย เช่น `.exe` (HTTP 400)
- [x] ทดสอบความปลอดภัย: ป้องกัน **Path Traversal Attacks** (HTTP 404/403)
- [x] ทดสอบการลบไฟล์ผ่าน API (`/api/delete`)

---

## 🔒 ข้อควรระวังด้านความปลอดภัย (Security Notice)

> ⚠️ **คำเตือน:** เซิร์ฟเวอร์นี้ออกแบบขึ้นมาสำหรับใช้งานส่วนตัวภายในเครือข่ายวงแลนเฉพาะกิจ (Private Wi-Fi Hotspot) เท่านั้น **ห้ามเปิด Port Forwarding หรือนำเซิร์ฟเวอร์นี้ไปเผยแพร่สู่ Public Internet โดยเด็ดขาด** เนื่องจากไม่มีระบบ Authentication/Login เพื่อความสะดวกรวดเร็วในการส่งเพลงเข้าจอรถยนต์
