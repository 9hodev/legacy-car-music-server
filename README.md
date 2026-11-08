# Local Music Drop Server & Audio Studio 🎵🚗🎛️

> **A zero-dependency HTTP Music Server & Audio Studio for macOS & older Android Head Units over Wi-Fi Hotspot.**
> ส่งไฟล์เพลงและประมวลผลเสียง (Convert, Optimize, Merge, Crossfade) จาก Mac ไปยังจอรถยนต์ Android รุ่นเก่าผ่าน Wi-Fi Hotspot โดยไม่ต้องต่อเน็ต และไม่พึ่งพา Cloud

---

## 📌 สรุปคุณสมบัติใหม่ (Audio Studio Upgrade)

1. **File Management: Rename (เปลี่ยนชื่อไฟล์อย่างปลอดภัย):**
   - ปุ่ม **Rename** พร้อมหน้าต่าง Modal
   - ปรับเปลี่ยนชื่อไฟล์ได้โดยยังคงนามสกุลไฟล์เสียงเดิมไว้เสมอ (Preserve original extension)
   - ป้องกัน Path Traversal, ป้องกันชื่อซ้ำ, รองรับภาษาไทย/Unicode และช่องว่าง
   - **File Locking:** ป้องกันการเปลี่ยนชื่อหรือลบไฟล์ที่กำลังอยู่ในกระบวนการ Convert/Merge
2. **Audio Optimization / Conversion (บีบอัดและแปลงไฟล์เสียง):**
   - รองรับ Input: `MP3`, `WAV`, `M4A`, `AAC`, `FLAC`, `OGG`, `OPUS`
   - รองรับ Output: `MP3`, `M4A/AAC`, `OGG`, `WAV`, `FLAC`
   - ปรับ Bitrate (320k, 256k, 192k, 128k, 96k), Sample rate (44.1kHz, 48kHz), Channels (Stereo, Mono)
   - ประมวลผลแบบ Background Task ผ่าน FFmpeg (ไม่บล็อก HTTP Server)
   - แสดง Progress Bar เรียลไทม์ คำนวณเปอร์เซ็นต์การลดขนาดไฟล์ (File Size Reduction %)
   - แจ้งเตือนกรณีแปลงไฟล์ Lossy &harr; Lossy เพื่อแจ้งเตือนการลดทอนของคุณภาพเสียง
   - ปลอดภัย: ไม่เขียนทับไฟล์เดิมเว้นแต่ผู้ใช้จะระบุอย่างชัดเจน (Default preserve original)
3. **Audio Merge Studio (`/studio`):**
   - หน้าเฉพาะสำหรับรวมไฟล์เพลงหลายแทร็ก (Mixed Format: เช่น MP3 + WAV + M4A + FLAC + OGG)
   - **Queue Drag & Drop:** จัดเรียงลำดับเพลงในคิวได้อิสระด้วยการลากวาง หรือกดปุ่มเลื่อนขึ้น/ลง
   - **Normalized Decoding:** ใช้ FFmpeg `filter_complex` แปลงสตรีมเสียงทั้งหมดให้มี Sample rate และ Channel layout เดียวกันก่อนรวมเสียง (ไม่ต่อดิบแบบ Byte Concatenation)
   - **Seamless Concat & Silence Gap:** แทรกช่วงเวลาเงียบ (Silence 1s, 2s, 3s, 5s) คั่นระหว่างแทร็กได้
   - **Acrossfade Transitions:** เฟดเสียงเชื่อมต่อระหว่างเพลง (Crossfade 1s - 5s) อย่างนุ่มนวล
   - บันทึกไฟล์ที่รวมแล้วลงโฟลเดอร์ `music/` ทันที พร้อมปุ่มดาวน์โหลดและเปิดดูบนจอรถยนต์
4. **รักษาความเข้ากันได้ 100% กับจอรถยนต์ Android รุ่นเก่า (Android 4.4 – 8.0):**
   - หน้าจอรถยนต์ (`/`) ยังคงทำงานแบบ **Zero-JS** ด้วย Direct HTML Anchor `<a href="/download/..." download>`
   - ปุ่มดาวน์โหลดขนาดใหญ่พิเศษ คอนทราสต์สูง อ่านง่ายและกดง่ายบนจอสัมผัส

---

## 🔧 การติดตั้ง FFmpeg (FFmpeg Installation)

ระบบเสียงของ Audio Studio ประมวลผลบนเครื่องเซิร์ฟเวอร์ Mac/Host โดยใช้ FFmpeg:

### บน macOS (แนะนำผ่าน Homebrew):
```bash
brew install ffmpeg
```

### บน Windows:
```powershell
winget install Gyan.FFmpeg
```

### บน Linux (Ubuntu/Debian):
```bash
sudo apt update && sudo apt install -y ffmpeg
```

*(หมายเหตุ: หากยังไม่ได้ติดตั้ง FFmpeg เซิร์ฟเวอร์ยังคงสามารถรันฟังก์ชัน อัปโหลด, ดาวน์โหลด, และสตรีมมิ่งเพลงไปยังจอรถยนต์ได้ตามปกติ)*

---

## 🚀 วิธีเริ่มต้นใช้งาน (Quick Start)

รันเซิร์ฟเวอร์ด้วยคำสั่งเดียว:

```bash
python3 server.py
```

*(หรือระบุพอร์ต เช่น `python3 server.py 8080`)*

เมื่อเริ่มทำงาน หน้าจอ Terminal จะแสดงข้อมูลการเข้าถึง:

```text
==================================================================
   LOCAL MUSIC DROP SERVER & AUDIO STUDIO (macOS & Car)
==================================================================
 * Status         : Running
 * Port           : 8000
 * FFmpeg Engine  : Available (Ready)
 * Music Folder   : /Users/.../music

 [Access URLs]
 -> Android Car Screen : http://192.168.43.50:8000/
 -> Audio Studio (Mac) : http://192.168.43.50:8000/studio
                         http://localhost:8000/studio
 -> Mac Upload/Admin   : http://192.168.43.50:8000/admin
                         http://localhost:8000/admin
==================================================================
```

---

## 📡 สรุป API Endpoints ทั้งหมด

### 1. หน้าเว็บหลัก (Pages)
- `GET /` หรือ `/index.html`: หน้าดาวน์โหลดสำหรับจอรถยนต์ (Server-rendered HTML list, Zero-JS ready)
- `GET /admin`: หน้าอัปโหลดและจัดการไฟล์ (Drag & Drop, Rename, Optimize)
- `GET /studio`: หน้า Audio Merge Studio (จัดคิวเพลง, รวมไฟล์, ทำ Crossfade)

### 2. ข้อมูลและดาวน์โหลด (Data & Downloads)
- `GET /api/files`: ดึงรายการไฟล์เสียง JSON (เพิ่ม Query `?meta=1` เพื่อดึง Duration และสถานะ Lock)
- `GET /api/tasks/<task_id>`: ตรวจสอบสถานะการแปลง/รวมไฟล์เสียง (Progress %, สถานะ, ขนาดไฟล์, ข้อผิดพลาด)
- `GET /download/<filename>`: สตรีมมิ่งและดาวน์โหลดไฟล์เสียง Chunked 64KB (รองรับ `Range: bytes=start-end`)

### 3. การประมวลผลและการจัดการ (Actions)
- `POST /api/upload`: อัปโหลดไฟล์เสียงแบบสตรีมมิ่งลงดิสก์โดยตรง (รองรับไฟล์ 100 MB+)
- `POST /api/rename`: เปลี่ยนชื่อไฟล์ (คงนามสกุลเดิม, ป้องกันชื่อซ้ำ, ตรวจสอบ Active Lock)
  ```json
  { "old_name": "song.wav", "new_name": "my_favorite_track.wav" }
  ```
- `POST /api/convert`: สั่งแปลงไฟล์หรือบีบอัดเสียงใน Background
  ```json
  {
    "source_filename": "track.wav",
    "output_format": "mp3",
    "target_filename": "track_opt.mp3",
    "bitrate": "192k",
    "sample_rate": 44100,
    "channels": 2,
    "overwrite": false
  }
  ```
- `POST /api/merge`: สั่งรวมไฟล์เสียงหลากฟอร์แมต (Mixed Format Merge)
  ```json
  {
    "source_filenames": ["intro.wav", "song.mp3", "outro.m4a"],
    "target_filename": "full_mix.mp3",
    "output_format": "mp3",
    "bitrate": "192k",
    "crossfade": 2.0,
    "silence": 0.0
  }
  ```
- `POST /api/delete`: ลบไฟล์เสียงออกจากเซิร์ฟเวอร์ (ป้องกันการลบไฟล์ที่กำลังถูกประมวลผล)
  ```json
  { "filename": "unwanted_song.mp3" }
  ```

---

## 🔒 สถาปัตยกรรมความปลอดภัย (Security & Reliability Architecture)

1. **Zero Shell Execution (`shell=False`):** คำสั่ง FFmpeg ทุกคำสั่งสร้างผ่าน List Arguments โดยไม่มีการเรียก Shell ป้องกันการถูกโจมตีด้วย OS Command Injection 100%
2. **Whitelist Profile Validation:** ไม่รับ Custom CLI String จากผู้ใช้ ยอมรับเฉพาะพารามิเตอร์ที่ผ่าน Whitelist เท่านั้น
3. **Strict Path Traversal Protection:** ตรวจสอบด้วย `os.path.commonpath()` และตัด Directory Component ทุกครั้ง
4. **File Locking (`locked_files`):** ไฟล์ที่กำลังถูกเปิดอ่านหรือเขียนโดย Background Task จะถูกล็อค ห้ามลบหรือเปลี่ยนชื่อจนกว่างานจะเสร็จ
5. **Memory Cap (O(1) RAM):** ทั้งการ Upload และ Download ใช้ Buffer 64 KB หน่วยความจำไม่บวมแม้ส่งไฟล์ขนาดใหญ่ 100 MB หรือระดับ GB
6. **Task ThreadPool Cap:** จำกัดการทำงานเบื้องหลังสูงสุด 2 งานพร้อมกัน เพื่อป้องกันการใช้ CPU หรือความร้อนบน Mac สูงเกินไป

---

## 🧪 การทดสอบระบบ (Automated Tests)

รันชุดทดสอบความเข้ากันได้และการประมวลผลเสียง 10 รายการ:

```bash
python3 test_audio_studio.py
```

รันชุดทดสอบ Integration พื้นฐาน (Streaming Upload 100MB, Range Header, Security Traversal):

```bash
python3 run_integration_test.py
```
