# Mô tả đầy đủ dự án: Hệ thống theo dõi nhịp thở bằng AI

> **Mục đích file này:** Đọc xong một lần là hiểu gần như mọi mặt của dự án — ý tưởng, phần cứng, phần mềm, cách đo nhịp thở, cách chạy, API, cảnh báo, hạn chế — **không cần kiến thức chuyên sâu**.

---

## 1. Dự án này làm gì?

Đây là hệ thống **theo dõi nhịp thở không tiếp xúc** (không đeo cảm biến lên người).

- Camera (ESP32-CAM) nhìn người nằm/ngồi.
- Máy tính dùng AI để tìm vùng ngực, đo chuyển động lên–xuống khi thở.
- Tính ra **BPM** = số lần thở mỗi phút.
- Lưu vào database, hiện lên **dashboard web**.
- Nếu nhịp thở **quá thấp** hoặc **quá cao** → gửi **email cảnh báo** kèm ảnh.

Ngoài ra còn có kênh phụ: cảm biến siêu âm (HC-SR04 + ESP8266) đo khoảng cách ngực–cảm biến, cũng tính BPM để **so sánh** với camera.

**Đề tài:** Hệ thống theo dõi nhịp thở không tiếp xúc sử dụng AI và IoT.  
**Nhóm:** Nhóm 12 — sinh viên ngành Mạng máy tính và Truyền thông dữ liệu.

---

## 2. Ý tưởng đo nhịp thở (giải thích đơn giản)

Khi người thở:

1. Lồng ngực **phồng lên / xẹp xuống**.
2. Camera thấy vùng ngực **dịch chuyển nhẹ theo chiều dọc**.
3. Phần mềm đo chuyển động đó theo thời gian → được một **đường sóng** (lên–xuống).
4. Lọc nhiễu, chỉ giữ tần số giống nhịp thở thật (~6–30 lần/phút).
5. Đếm các “đỉnh sóng” → nhân ra số lần thở/phút (**BPM**).

Với cảm biến siêu âm: khoảng cách tới ngực thay đổi khi thở → cũng ra đường sóng tương tự → dùng cùng cách lọc và đếm đỉnh.

---

## 3. Nhịp thở bình thường là bao nhiêu?

| Trạng thái | BPM (lần/phút) |
|------------|----------------|
| Người lớn nghỉ ngơi (tham khảo) | khoảng **12–20** |
| Hệ thống coi **bất thường** (gửi email) | **< 5** hoặc **> 25** |
| Dashboard tô màu cảnh báo trên số BPM | **< 10** hoặc **> 30** |

> Hai ngưỡng khác nhau có chủ đích: email chỉ khi thật sự lệch nhiều; giao diện cảnh báo sớm hơn một chút.

---

## 4. Kiến trúc tổng thể (nhìn toàn cục)

```
┌─────────────────┐     MJPEG stream      ┌──────────────────────────┐
│  ESP32-CAM      │ ───────────────────►  │  AI Worker (PC)          │
│  (camera WiFi)  │   http://IP/stream    │  breathing_worker.py     │
└─────────────────┘                       │  YOLO → ROI → motion →   │
                                          │  lọc tín hiệu → BPM      │
┌─────────────────┐     POST /distance    │                          │
│ ESP8266 +       │ ───────────────────►  │  ultrasonic_worker.py    │
│ HC-SR04         │   port 5002           │  (cùng pipeline lọc BPM) │
└─────────────────┘                       └────────────┬─────────────┘
                                                       │ POST /api/breathing
                                                       ▼
                                          ┌──────────────────────────┐
                                          │  Backend Flask (port 5000)│
                                          │  - Lưu MySQL              │
                                          │  - Kiểm tra cảnh báo      │
                                          │  - Gửi email nếu cần      │
                                          │  - Phục vụ dashboard web  │
                                          └────────────┬─────────────┘
                                                       │
                                          ┌────────────▼─────────────┐
                                          │  Dashboard trình duyệt   │
                                          │  http://localhost:5000   │
                                          └──────────────────────────┘
```

**Tóm lại 4 khối chính:**

| Khối | Vai trò |
|------|---------|
| Phần cứng IoT | Quay video / đo khoảng cách, gửi về máy tính |
| AI Worker | Xử lý video hoặc khoảng cách → ra BPM |
| Backend Flask | Nhận BPM, lưu DB, cảnh báo, API, giao diện |
| Dashboard | Người dùng xem BPM realtime + lịch sử |

---

## 5. Cấu trúc thư mục dự án

```
Nhóm 12- Hệ thống theo dõi nhịp thở bằng AI/
│
├── README.md                 ← Hướng dẫn ngắn (cài đặt, API)
├── MO_TA_DU_AN_DAY_DU.md     ← File bạn đang đọc (mô tả đầy đủ)
├── requirements.txt          ← Danh sách thư viện Python
├── esp32cam_stream.ino       ← Firmware nạp vào ESP32-CAM
├── yolo11n-pose.pt           ← Model YOLO Pose (cần tải về, đặt ở thư mục gốc)
│
├── ai_worker/                ← Phần “não AI” đo nhịp thở
│   ├── breathing_worker.py   ← Worker chính: ESP32-CAM → BPM
│   ├── ultrasonic_worker.py  ← Worker phụ: siêu âm → BPM
│   └── ai/
│       ├── pose_detector.py      ← Bọc YOLO Pose
│       ├── roi_extractor.py      ← Cắt vùng ngực từ khớp xương
│       ├── motion_tracker.py     ← Optical flow đo chuyển động dọc
│       ├── signal_filter.py      ← Lọc băng thông 0.1–0.5 Hz
│       └── breathing_rate.py     ← Đếm đỉnh sóng → BPM
│
├── backend/                  ← Server Flask + DB + email
│   ├── app.py                ← API + phục vụ dashboard
│   ├── models.py             ← Bảng breathing_records
│   ├── database.py           ← Kết nối MySQL
│   ├── init_db.py            ← Tạo bảng lần đầu
│   ├── alarm_manager.py      ← Quyết định có gửi cảnh báo không
│   ├── email_sender.py       ← Gửi Gmail kèm ảnh
│   ├── config.py             ← SMTP, email, ngưỡng
│   └── test_insert.py        ← Script thử ghi 1 bản ghi DB
│
├── dashboard/                ← Giao diện web
│   ├── templates/index.html
│   └── static/
│       ├── css/style.css
│       └── js/dashboard.js
│
├── tests/                    ← Script thử từng bước (webcam laptop)
│   ├── test_pose.py          ← Thử YOLO Pose
│   ├── test_keypoint.py      ← Thử đọc khớp vai/hông
│   └── test_roi.py           ← Thử ROI + motion + BPM (webcam)
│
└── captures/                 ← Ảnh chụp khi BPM bất thường (tự tạo)
```

---

## 6. Phần cứng cần có

### 6.1. ESP32-CAM (nguồn đo chính)

- Board: **AI Thinker ESP32-CAM** (cảm biến OV2640).
- Kết nối WiFi, phát **stream MJPEG** qua HTTP.
- Firmware: file `esp32cam_stream.ino`.

**Cấu hình quan trọng trong firmware:**

| Tham số | Giá trị | Vì sao |
|---------|---------|--------|
| Độ phân giải | VGA 640×480 | Đủ cho YOLO + optical flow, không quá nặng WiFi |
| JPEG quality | 12 (thang 0–63, số nhỏ = đẹp hơn) | Optical flow rất nhạy với “ô vuông” JPEG |
| FPS mục tiêu | ~12.5 (delay 80 ms) | Ổn định hơn là chạy quá nhanh |
| Endpoint | `/stream` | Worker đọc video từ đây |
| Kiểm tra sống | `/ping` → trả `OK` | Dễ kiểm tra camera còn sống |

**Trước khi nạp code:** sửa `WIFI_SSID` và `WIFI_PASSWORD` trong file `.ino`.  
**Khi nạp:** nối GPIO0 với GND, nạp xong thì tháo.

Sau khi ESP32-CAM kết nối WiFi, Serial Monitor in IP, ví dụ:

```text
Stream: http://192.168.x.x/stream
Ping:   http://192.168.x.x/ping
```

Worker mặc định đang trỏ tới (cần sửa cho đúng IP của bạn):

```text
http://172.20.10.4/stream
```

trong biến `ESPCAM_URL` ở đầu `breathing_worker.py`.

### 6.2. ESP8266 + HC-SR04 (nguồn đo phụ, tùy chọn)

- ESP8266 đo khoảng cách bằng siêu âm, gửi HTTP `POST` tới máy tính:
  - URL: `http://<IP_MÁY_TÍNH>:5002/distance`
  - Body JSON: `{ "distance_cm": 12.3 }`
- `ultrasonic_worker.py` nhận dữ liệu, tính BPM, gửi lên backend với `source: "ultrasonic"`.

> Trong repo **không có** firmware ESP8266; chỉ có worker phía máy tính. Cần tự viết/nạp firmware gửi `distance_cm`.

### 6.3. Máy tính (PC)

- Chạy Python: AI Worker + Backend Flask.
- Có MySQL (ví dụ MySQL Workbench).
- Cùng mạng WiFi với ESP32-CAM (để đọc stream).

---

## 7. Pipeline AI đo nhịp thở từ camera (chi tiết từng bước)

Đây là trái tim của dự án. Worker: `ai_worker/breathing_worker.py`.

### Bước 1 — Đọc video từ ESP32-CAM

- Mở URL MJPEG bằng OpenCV.
- Buffer nhỏ (2 frame) để giảm độ trễ.
- Nếu mất kết nối → tự thử kết nối lại (tối đa 10 lần).
- Theo dõi FPS: nếu trung bình **< 5 FPS** trong 10 giây → in cảnh báo (tín hiệu có thể kém).

### Bước 2 — Nhận dạng tư thế (YOLO Pose)

- Model: **`yolo11n-pose.pt`** (YOLO11 nano pose, thư viện Ultralytics).
- Tìm người trong khung hình, lấy **keypoints** (khớp xương).
- Dùng 4 điểm chính:
  - Vai trái / vai phải (index 5, 6)
  - Hông trái / hông phải (index 11, 12)

File hỗ trợ: `ai/pose_detector.py` (bọc model; worker chính gọi YOLO trực tiếp).

### Bước 3 — Cắt vùng ngực (ROI)

File: `ai/roi_extractor.py`

- Trái–phải: từ vai trái đến vai phải.
- Trên–dưới: từ vai xuống khoảng **35%** khoảng cách vai → hông.

→ Chỉ quan sát vùng ngực, bỏ đầu/tay/nền gây nhiễu.

**Tối ưu runtime:**

- Không chạy YOLO mỗi frame (nặng). Mặc định **mỗi 10 frame** cập nhật ROI một lần (`--roi-update-every 10`).
- Khi ROI dịch chuyển, dùng **làm mượt EMA** (`--roi-smoothing 0.3`) để khung không nhảy giật.

### Bước 4 — Đo chuyển động (Optical Flow)

File: `ai/motion_tracker.py`

1. Đổi ROI sang ảnh xám.
2. Resize về 200×200 (ổn định kích thước).
3. Làm mờ Gaussian:
   - Webcam: kernel 5×5
   - **ESP32-CAM: 7×7** (JPEG nhiễu hơn)
4. Tính **Farneback optical flow** giữa frame trước và frame sau.
5. Lấy **trung vị** của chuyển động theo chiều dọc (trục Y).

Mỗi frame có ROI hợp lệ → thêm 1 mẫu `(thời gian, giá trị motion)` vào khối tín hiệu.

### Bước 5 — Gom khối 60 giây

- Mặc định mỗi **60 giây** (`--interval 60`) xử lý một khối **không chồng lặp**.
- Cần ít nhất ~10 mẫu; nếu quá ít thì bỏ qua khối đó.

### Bước 6 — Lọc tín hiệu

File: `ai/signal_filter.py`

**Mục tiêu:** chỉ giữ tần số giống nhịp thở thật:

- Thấp: **0.1 Hz** ≈ 6 lần/phút  
- Cao: **0.5 Hz** ≈ 30 lần/phút  

**Cách làm:**

1. Nếu có timestamp → **resample** về lưới thời gian đều (vì FPS WiFi thường không đều).
2. Lọc **Butterworth bandpass** bậc 3.
3. Nếu không đủ mẫu / FPS quá thấp / lọc lỗi → fallback **Savitzky–Golay**.

### Bước 7 — Ước lượng BPM

File: `ai/breathing_rate.py`

- Dùng `find_peaks` (SciPy).
- Khoảng cách tối thiểu giữa 2 đỉnh ≈ **1.5 giây** (không cho BPM “ảo” > 40).
- Chỉ tính đỉnh **nổi bật** so với độ dao động chung (`prominence`).
- Công thức:  
  `BPM = (số đỉnh / thời lượng giây) × 60`

### Bước 8 — Gửi lên backend

- `POST http://127.0.0.1:5000/api/breathing`
- Body gồm `bpm`, `source: "camera_ai"`, và đường dẫn ảnh nếu bất thường.
- Nếu BPM **< 5** hoặc **> 25** → lưu ảnh frame vào thư mục `captures/` rồi gửi kèm path.

### Bốc 9 — Hiển thị khi chạy worker

- Cửa sổ OpenCV: video + khung ROI xanh + giá trị motion.
- Cửa sổ Matplotlib: sóng thô và sóng đã lọc (cập nhật mỗi khối).
- Nhấn **Esc** hoặc Ctrl+C để dừng.

---

## 8. Worker siêu âm (kênh phụ)

File: `ultrasonic_worker.py`

| Mục | Chi tiết |
|-----|----------|
| Nghe dữ liệu | Flask nhỏ port **5002**, `POST /distance` |
| Kiểm tra | `GET /status` → số mẫu trong buffer |
| Xử lý | Đảo dấu khoảng cách (ngực phồng → khoảng cách giảm → tín hiệu tăng), chuẩn hóa, bandpass, đếm đỉnh |
| Lọc nhiễu thêm | Nếu nhịp không đều mạnh (`regularity > 0.5`) → bỏ khối |
| Gửi API | Cùng `/api/breathing` nhưng `source: "ultrasonic"` |
| Chạy song song | Có thể chạy cùng lúc với `breathing_worker.py` để so sánh trên dashboard |

---

## 9. Backend Flask

File chính: `backend/app.py`  
Chạy tại: **`http://0.0.0.0:5000`** (mở `http://localhost:5000`)

### 9.1. Các API

| Method | Đường dẫn | Việc làm |
|--------|-----------|----------|
| GET | `/` | Trang dashboard |
| GET | `/api/latest` | Bản ghi BPM mới nhất |
| GET | `/api/history?limit=100` | Lịch sử (mặc định 100) |
| POST | `/api/breathing` | Nhận BPM từ worker, lưu DB, chạy cảnh báo |

**POST `/api/breathing` — body ví dụ:**

```json
{
  "bpm": 18.4,
  "source": "camera_ai",
  "image": "captures/20260722_140530.jpg",
  "note": "tuỳ chọn"
}
```

- Bắt buộc: `bpm` (số).
- Không bắt buộc: `source` (mặc định `camera_ai`), `note`, `image`.
- Thành công → HTTP **201** + JSON bản ghi vừa tạo.
- Thiếu `bpm` → **400**.

**GET `/api/latest`:** nếu chưa có dữ liệu → **404** `{ "message": "Chưa có dữ liệu" }`.

**JSON trả về (mẫu):**

```json
{
  "id": 10,
  "bpm": 18.4,
  "source": "camera_ai",
  "note": null,
  "recorded_at": "2026-07-22T14:05:30"
}
```

### 9.2. Database (MySQL)

Kết nối trong `backend/database.py`:

```text
mysql+pymysql://root:<mật_khẩu>@localhost/breathing_monitor
```

Bảng `breathing_records` (`models.py`):

| Cột | Kiểu | Ý nghĩa |
|-----|------|---------|
| id | INT, PK, tự tăng | Khóa chính |
| bpm | FLOAT | Nhịp thở |
| source | VARCHAR(50) | `camera_ai` / `ultrasonic` / … |
| note | VARCHAR(255), null | Ghi chú tùy chọn |
| created_at | DATETIME | Thời điểm ghi |

Tạo database thủ công:

```sql
CREATE DATABASE breathing_monitor;
```

Tạo bảng:

```bash
python backend/init_db.py
```

### 9.3. Hệ thống cảnh báo email

**Luồng:**

1. Worker gửi BPM (+ ảnh nếu bất thường).
2. `app.py` gọi `alarm_manager.process(bpm, image_path)`.
3. Nếu BPM **< 5** hoặc **> 25** và **chưa gửi mail lần này** → gọi `email_sender.send_breathing_alert`.
4. Khi BPM trở lại bình thường → reset cờ, lần bất thường sau mới gửi lại.

**Email (`email_sender.py` + `config.py`):**

- SMTP Gmail: `smtp.gmail.com:587` (STARTTLS).
- Nội dung HTML: tiêu đề cảnh báo, BPM, thời gian, ảnh đính kèm inline.
- Cấu hình: `SENDER_EMAIL`, `APP_PASSWORD` (App Password Gmail), `RECEIVER_EMAIL`.

> **Lưu ý bảo mật:** `backend/config.py` đang chứa mật khẩu ứng dụng Gmail dạng plaintext. Không nên đẩy lên Git công khai; nên dùng biến môi trường hoặc file local không commit.

Ngưỡng trong `config.py` có `BREATHING_THRESHOLD = 10` nhưng **logic gửi mail thực tế** dùng `LOW_THRESHOLD = 5` và `HIGH_THRESHOLD = 25` trong `alarm_manager.py`.

---

## 10. Dashboard web

| File | Vai trò |
|------|---------|
| `dashboard/templates/index.html` | Bố cục trang |
| `dashboard/static/css/style.css` | Giao diện (xanh teal, font Quicksand/Inter) |
| `dashboard/static/js/dashboard.js` | Lấy API, cập nhật số, vẽ biểu đồ |

**Người dùng thấy:**

- Số BPM lớn ở giữa + vòng “thở” trang trí.
- Thời gian cập nhật gần nhất + nguồn (`camera_ai` / `ultrasonic`).
- Trạng thái: “Đang giám sát” / “Mất kết nối với cảm biến”.
- Thống kê: trung bình / thấp nhất / cao nhất (trên 100 bản ghi gần nhất).
- Biểu đồ lịch sử (Chart.js): zoom cuộn chuột, kéo pan, double-click hoặc nút Reset zoom.

**Cách hoạt động phía trình duyệt:**

- Mỗi **5 giây** gọi `/api/latest` và `/api/history?limit=100`.
- Coi “mất kết nối” nếu bản ghi mới nhất cũ hơn **90 giây** (vì worker gửi mỗi ~60 giây + dự phòng trễ).
- BPM **< 10** hoặc **> 30** → tô class cảnh báo trên số lớn.

---

## 11. Thư viện Python (requirements.txt)

| Thư viện | Dùng để |
|----------|---------|
| Flask | Backend + (ultrasonic) receiver |
| SQLAlchemy + PyMySQL | MySQL |
| opencv-python | Đọc camera/stream, xử lý ảnh |
| numpy, scipy | Tín hiệu, lọc, tìm đỉnh |
| matplotlib | Vẽ sóng khi chạy worker |
| ultralytics | YOLO Pose |
| torch, torchvision | Backend cho YOLO |
| requests | Worker gọi API |
| pillow | Xử lý ảnh hỗ trợ |

---

## 12. Cách cài đặt và chạy (từ đầu đến cuối)

### Bước A — Môi trường Python

```bash
cd "thư_mục_gốc_dự_án"
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
pip install -r requirements.txt
```

### Bước B — Model YOLO

Tải / đặt file **`yolo11n-pose.pt`** vào **thư mục gốc** dự án (cùng cấp với `ai_worker/`, `backend/`).

### Bước C — MySQL

1. Tạo DB `breathing_monitor`.
2. Sửa user/mật khẩu trong `backend/database.py`.
3. Chạy: `python backend/init_db.py`

### Bước D — Email (nếu dùng cảnh báo)

Sửa `backend/config.py`: email gửi, App Password Gmail, email nhận.

### Bước E — ESP32-CAM

1. Sửa WiFi trong `esp32cam_stream.ino`, nạp firmware.
2. Lấy IP từ Serial Monitor.
3. Sửa `ESPCAM_URL` trong `breathing_worker.py` (hoặc chạy với `--espcam http://IP/stream`).
4. Thử trình duyệt: `http://IP/ping` phải thấy `OK`.

### Bước F — Chạy hệ thống (2 cửa sổ terminal)

**Terminal 1 — Backend + dashboard:**

```bash
python backend/app.py
```

Mở: http://localhost:5000

**Terminal 2 — AI camera:**

```bash
python ai_worker/breathing_worker.py
```

hoặc:

```bash
python ai_worker/breathing_worker.py --espcam http://192.168.1.50/stream --api http://127.0.0.1:5000 --interval 60
```

**Tùy chọn — siêu âm:**

```bash
python ai_worker/ultrasonic_worker.py
```

---

## 13. Tham số dòng lệnh hữu ích (breathing_worker)

| Tham số | Mặc định | Ý nghĩa |
|---------|----------|---------|
| `--api` | `http://127.0.0.1:5000` | Địa chỉ backend |
| `--espcam` | giá trị `ESPCAM_URL` trong file | URL stream |
| `--interval` | 60 | Độ dài mỗi khối tính BPM (giây) |
| `--roi-update-every` | 10 | Bao nhiêu frame mới chạy lại YOLO |
| `--roi-smoothing` | 0.3 | Độ mượt khi ROI dịch (0–1) |

---

## 14. Kiểm thử / script thử nghiệm

Trong `tests/` (thường dùng **webcam laptop** `VideoCapture(0)`, không phải ESP32):

| Script | Mục đích học/kiểm tra |
|--------|------------------------|
| `test_pose.py` | Xem YOLO vẽ khung xương realtime |
| `test_keypoint.py` | In tọa độ vai trái/phải |
| `test_roi.py` | Khóa ROI ngực, đo motion, vẽ sóng + in BPM sau ~900 frame |

`backend/test_insert.py`: ghi thử 1 bản ghi BPM = 18.5 vào DB.

**Gợi ý điều kiện đo thật (từ README):**

- Người nằm ngửa, yên.
- Camera cách khoảng **0.5–1 m**.
- Ánh sáng ổn định.
- Thử thêm: xoay đầu, cử động tay nhẹ — xem hệ thống chịu nhiễu thế nào.

---

## 15. Luồng dữ liệu end-to-end (một vòng đầy đủ)

1. ESP32-CAM chụp JPEG → gửi liên tục qua `/stream`.
2. Worker đọc frame → YOLO tìm người → cắt ROI ngực.
3. Optical flow → giá trị chuyển động dọc mỗi frame.
4. Sau 60 giây: lọc bandpass → đếm đỉnh → ra BPM.
5. Nếu bất thường: lưu ảnh vào `captures/`.
6. `POST /api/breathing` → Flask lưu MySQL.
7. `alarm_manager` quyết định gửi Gmail hay không.
8. Dashboard mỗi 5 giây đọc `/api/latest` + `/api/history` → cập nhật số và biểu đồ.

---

## 16. Công nghệ tóm tắt (bảng “một dòng”)

| Lớp | Công nghệ |
|-----|-----------|
| Phần cứng camera | ESP32-CAM, OV2640, WiFi, MJPEG HTTP |
| Phần cứng siêu âm (phụ) | ESP8266 + HC-SR04 |
| Thị giác máy tính | OpenCV, Farneback optical flow |
| AI Pose | Ultralytics YOLO11 Pose (`yolo11n-pose.pt`) |
| Xử lý tín hiệu | NumPy, SciPy (Butterworth, Savitzky–Golay, find_peaks) |
| Backend | Flask |
| Database | MySQL + SQLAlchemy + PyMySQL |
| Frontend | HTML/CSS/JS, Chart.js + zoom plugin |
| Cảnh báo | SMTP Gmail + MIME (HTML + ảnh) |
| Ngôn ngữ | Python (PC), C++/Arduino (ESP32) |

---

## 17. Điểm mạnh / hạn chế / hướng phát triển

### Điểm mạnh

- Đo **không tiếp xúc** — phù hợp theo dõi khi ngủ/nghỉ.
- Pipeline tín hiệu có **bandpass + prominence** (giảm nhiễu “nhảy số”).
- Tự thích nghi FPS thấp của ESP32-CAM (tính fps từ timestamp).
- Có **hai nguồn** (camera + siêu âm) để đối chiếu.
- Có **cảnh báo email + ảnh** khi bất thường.
- Dashboard realtime dễ quan sát.

### Hạn chế / lưu ý thực tế

- Cần người **nằm/ngồi tương đối yên**; cử động mạnh làm sai BPM.
- Ánh sáng và chất lượng WiFi ảnh hưởng FPS và độ chính xác.
- YOLO + torch khá nặng CPU/GPU máy tính.
- Chỉ theo dõi tốt khi **nhìn thấy ngực** (tư thế, chăn đắp có thể che).
- Cảnh báo email dùng cờ toàn cục trong process Flask (`mail_sent`) — phù hợp demo 1 máy; chưa thiết kế multi-user/multi-patient.
- README còn ghi tên file cũ `breathing_ai_worker.py`; file thật là **`breathing_worker.py`**.
- Một số ngưỡng rải rác ở nhiều file (5/25 vs 10/30) — cần nhớ khi chỉnh.

### Hướng phát triển (đã gợi ý trong README / code)

- MQTT IoT
- Nhiều bệnh nhân đồng thời
- Telegram / thêm kênh cảnh báo
- Lưu trữ cloud
- Phân tích xu hướng dài hạn
- Ẩn bí mật cấu hình khỏi source code

---

## 18. “Bản đồ” file quan trọng — đọc gì khi cần hiểu sâu hơn

| Muốn hiểu… | Đọc file |
|------------|----------|
| Toàn bộ luồng camera → BPM | `ai_worker/breathing_worker.py` |
| Cách cắt ngực | `ai_worker/ai/roi_extractor.py` |
| Cách đo chuyển động | `ai_worker/ai/motion_tracker.py` |
| Cách lọc sóng thở | `ai_worker/ai/signal_filter.py` |
| Cách đếm BPM | `ai_worker/ai/breathing_rate.py` |
| API + dashboard server | `backend/app.py` |
| Bảng DB | `backend/models.py` |
| Khi nào gửi mail | `backend/alarm_manager.py` |
| Nội dung email | `backend/email_sender.py` |
| Giao diện cập nhật số | `dashboard/static/js/dashboard.js` |
| Camera IoT | `esp32cam_stream.ino` |
| Siêu âm | `ai_worker/ultrasonic_worker.py` |

---

## 19. Thuật ngữ nhanh (không cần học trước)

| Thuật ngữ | Nghĩa đời thường |
|-----------|------------------|
| BPM | Số lần thở mỗi phút |
| ROI | Vùng quan tâm — ở đây là khung quanh ngực |
| Keypoint / Pose | Điểm khớp xương mà AI ước lượng trên người |
| Optical flow | Ước lượng “điểm ảnh nào dịch chuyển đi đâu” giữa 2 frame |
| Bandpass filter | Chỉ giữ sóng trong khoảng tần số hữu ích, bỏ nhiễu |
| Peak | Đỉnh sóng — mỗi đỉnh ≈ một nhịp thở |
| MJPEG stream | Video gửi liên tục dạng chuỗi ảnh JPEG qua mạng |
| Worker | Chương trình chạy nền chuyên xử lý (không phải trang web) |
| Backend / API | Phần server nhận–lưu–trả dữ liệu |
| Dashboard | Màn hình giám sát trên trình duyệt |

---

## 20. Checklist “đã hiểu dự án” (tự kiểm)

Sau khi đọc file này, bạn nên trả lời được:

1. Dự án đo nhịp thở **không đeo cảm biến**, bằng camera (và tùy chọn siêu âm).  
2. AI tìm **vùng ngực**, đo **chuyển động dọc**, lọc sóng, **đếm đỉnh** → BPM.  
3. Mỗi ~**60 giây** gửi một BPM lên Flask, lưu MySQL, hiện dashboard.  
4. BPM **< 5 hoặc > 25** → có thể **gửi email + ảnh**.  
5. Để chạy cần: MySQL, `yolo11n-pose.pt`, ESP32-CAM đúng IP, `app.py` + `breathing_worker.py`.

---

*File mô tả này được tổng hợp từ toàn bộ mã nguồn và README hiện có trong repository. Nếu code thay đổi sau này, hãy cập nhật lại các ngưỡng, tên file và tham số cho khớp.*
