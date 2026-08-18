# WORKFLOW HỆ THỐNG ESP32 AUDIO

## 1. Kiến trúc tổng thể

Web Node.js
↓
Backend Python
↓
Mosquitto MQTT
↓
ESP32 Arduino
↓
Loa

Song song:

Backend Python
├── Lưu File Audio thật
└── Gửi Filename + Metadata lên Cloud Database

Luồng từ ESP32 lên điện thoại:

ESP32
↓
Mosquitto MQTT
↓
Backend Python
↓
Cloud Service
↓
Điện thoại


## 2. Luồng Text → Loa

User nhập Text trên Web
↓
Web Node.js
↓
Backend Python
↓
Text-to-Speech
↓
Tạo File Audio
↓
Lưu File Audio tại Backend
↓
Trích xuất Metadata
↓
Lưu Filename + Metadata lên Cloud Database
↓
Backend tạo MQTT Command
↓
Mosquitto MQTT
↓
ESP32 nhận Command
↓
ESP32 tải File Audio từ Backend
↓
ESP32 phát Audio
↓
Loa


Ví dụ dữ liệu lưu trên Cloud:

{
  "filename": "tts_001.mp3",
  "type": "tts",
  "duration": 5.2,
  "format": "mp3",
  "status": "ready"
}


## 3. Luồng File Audio → Loa

User Upload File Audio
↓
Web Node.js
↓
Backend Python
↓
Kiểm tra File
↓
Lưu File Audio thật tại Backend
↓
Trích xuất Metadata
↓
Lưu Filename + Metadata lên Cloud Database
↓
Backend tạo MQTT Command
↓
Mosquitto MQTT
↓
ESP32 nhận Command
↓
ESP32 tải File Audio từ Backend
↓
ESP32 phát Audio
↓
Loa


Ví dụ Metadata:

{
  "filename": "music.mp3",
  "type": "uploaded",
  "duration": 120,
  "format": "mp3",
  "sample_rate": 44100,
  "size": 5242880,
  "status": "ready"
}


## 4. Cách lưu dữ liệu

### Backend Python

Backend lưu File Audio thật.

Ví dụ:

backend/
└── audio/
    ├── music.mp3
    ├── alarm.wav
    └── tts_001.mp3


### Cloud Database

Cloud KHÔNG lưu File Audio thật.

Cloud chỉ lưu:

- Filename
- Metadata
- Trạng thái
- Device ID nếu cần
- Thời gian tạo nếu cần


Ví dụ:

{
  "filename": "music.mp3",
  "duration": 120,
  "format": "mp3",
  "status": "ready"
}


## 5. Luồng Web chọn File đã có

Web lấy danh sách Filename từ Cloud Database
↓
Hiển thị danh sách File cho User
↓
User chọn File
↓
Web gửi Filename xuống Backend
↓
Backend tìm File Audio thật
↓
Backend tạo URL / đường dẫn File
↓
Gửi MQTT Command
↓
ESP32 nhận Command
↓
ESP32 tải File từ Backend
↓
Phát ra Loa


Ví dụ MQTT Command:

{
  "command": "play",
  "filename": "music.mp3",
  "audio_url": "http://backend/audio/music.mp3"
}


## 6. Luồng điều khiển Web → ESP32

User thao tác trên Web
↓
Web Node.js
↓
Backend Python
↓
Tạo Command JSON
↓
MQTT Publish
↓
Mosquitto Broker
↓
ESP32 Subscribe
↓
ESP32 thực hiện lệnh
↓
ESP32 gửi Status xác nhận
↓
Backend Python
↓
Web cập nhật trạng thái


Các lệnh có thể gồm:

- play
- stop
- pause
- volume


## 7. Luồng ESP32 → Cloud → Điện thoại

ESP32
↓
Tạo Status JSON
↓
MQTT Publish
↓
Mosquitto Broker
↓
Backend Python Subscribe
↓
Xử lý trạng thái
↓
Cloud Service
├── Lưu trạng thái nếu cần
└── Gửi Push Notification
       ↓
   Điện thoại


Ví dụ Status:

{
  "device_id": "esp32_01",
  "status": "online",
  "speaker": "playing",
  "current_file": "music.mp3"
}


## 8. Các thông báo lên điện thoại

- ESP32 đã kết nối
- ESP32 mất kết nối
- Bắt đầu phát Audio
- Phát Audio hoàn tất
- Không tải được File
- Phát Audio thất bại
- ESP32 gặp lỗi


## 9. MQTT Topic đề xuất

### esp32/command

Backend → ESP32

Dùng cho:

- play
- pause
- stop
- volume


### esp32/status

ESP32 → Backend

Dùng cho:

- online
- offline
- playing
- stopped
- error


## 10. Workflow tổng thể cuối cùng

                         [Web Node.js]
                               ↓
                          HTTP / REST
                               ↓
                       [Backend Python]
                         ↓          ↓
                Audio File      Filename + Metadata
                lưu tại BE            ↓
                         ↓       [Cloud Database]
                         ↓
                  [Mosquitto MQTT]
                         ↓
                       [ESP32]
                         ↓
                       [Loa]


Luồng thông báo:

ESP32
↓
MQTT
↓
Backend Python
↓
Cloud Service
↓
Push Notification
↓
Điện thoại


## 11. Ba luồng chính cần nhớ

### Luồng 1: Text → Loa

Text
↓
Web
↓
Backend
↓
Text-to-Speech
↓
Lưu Audio ở Backend
↓
Lưu Filename + Metadata trên Cloud
↓
MQTT
↓
ESP32
↓
Loa


### Luồng 2: File Audio → Loa

File Audio
↓
Web
↓
Backend
↓
Lưu Audio ở Backend
↓
Trích xuất Metadata
↓
Lưu Filename + Metadata trên Cloud
↓
MQTT
↓
ESP32
↓
Loa


### Luồng 3: ESP32 → Điện thoại

ESP32
↓
MQTT
↓
Backend
↓
Cloud Service
↓
Push Notification
↓
Điện thoại


## 12. Nguyên tắc quan trọng

File Audio thật
→ chỉ lưu tại Backend Python

Cloud Database
→ chỉ lưu Filename + Metadata + Status

MQTT
→ chỉ gửi Command / Status / URL / Filename

ESP32
→ nhận lệnh, tải File từ Backend và phát ra Loa


## 13. Luồng mới: Micro INMP441 → Web Dashboard

Người nói vào Micro INMP441
↓
ESP32 đọc I2S và chuyển mẫu thành PCM s16le
↓
ESP32 chia PCM thành các chunk 512 samples
↓
Mosquitto nhận MQTT `audio/start`, `audio/chunk/{recording_id}/{sequence}`, `audio/end`
↓
Backend Python kiểm tra sequence và ghép các chunk
├── Đóng gói WAV: 16 kHz, Mono, 16-bit
├── Lưu File thật: `backend/storage/audio/rec_xxx.wav`
└── Lưu Metadata: `backend/storage/metadata.json`
↓
Web gọi `GET /api/v1/audio` và cập nhật danh sách
↓
User bấm nghe bằng `<audio controls>` hoặc tải qua endpoint download

Web vẫn chỉ gọi Backend API. File WAV hoàn chỉnh không đi qua MQTT.

Để tạo phiên ghi:

```text
Web → POST /api/v1/devices/{device_id}/record/start
    → Backend → MQTT START_RECORDING
    → ESP32 publish PCM chunks
    → Backend finalize WAV
```
