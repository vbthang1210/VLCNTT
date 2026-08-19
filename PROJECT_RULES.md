# PROJECT_RULES.md
# ESP32 AUDIO SYSTEM — ARCHITECTURE & TECHNICAL RULES

## 1. Mục tiêu hệ thống

### Text → Loa

```text
User nhập Text
↓
Web Node.js
↓
Backend Python
↓
Text-to-Speech
↓
Lưu Audio tại Backend
↓
Lưu Filename + Metadata lên Cloud
↓
MQTT Command
↓
ESP32
↓
HTTP Audio Streaming từ Backend
↓
Decode
↓
I2S
↓
Loa
```

### File Audio → Loa

```text
User Upload File Audio
↓
Web Node.js
↓
Backend Python
↓
Validate File
↓
Lưu Audio tại Backend
↓
Trích xuất Metadata
↓
Lưu Filename + Metadata lên Cloud
↓
MQTT Command
↓
ESP32
↓
HTTP Audio Streaming từ Backend
↓
Decode
↓
I2S
↓
Loa
```

### ESP32 → Điện thoại

```text
ESP32
↓
Mosquitto MQTT
↓
Backend Python
↓
Cloud Service
↓
Push Notification
↓
Điện thoại
```

---

# 2. Kiến trúc chốt

Hệ thống gồm:

- Web: Node.js
- Backend: Python
- MQTT Broker: Mosquitto
- Device: ESP32 dùng Arduino
- Backend Audio Storage: lưu File Audio thật
- Cloud Service: service ngoài Backend, ví dụ Firebase

Cloud Service có thể gồm:

```text
Firebase
├── Firestore
└── Firebase Cloud Messaging
```

Cloud KHÔNG phải submodule nằm trong Backend.

```text
[Web Node.js]
      ↓
   HTTP / REST
      ↓
[Backend Python]
   │
   ├── Audio Storage
   ├── TTS Service
   ├── Metadata Service
   ├── MQTT Client
   │
   └──────────────→ [Cloud Service]
                         ├── Database
                         └── Notification
   │
   ↓
[Mosquitto Broker]
      ↓
    [ESP32]
      ↓
     [Loa]
```

---

# 3. Nguyên tắc lưu dữ liệu

## File Audio thật

Chỉ lưu tại Backend.

```text
backend/
└── storage/
    └── audio/
        ├── audio_a31f.mp3
        ├── audio_98ef.wav
        └── tts_33ab.mp3
```

Không upload File Audio thật lên Cloud.

## Cloud Database

Chỉ lưu dữ liệu nhẹ:

- audio_id
- filename
- original_filename
- duration
- format
- sample_rate
- size
- status
- device_id nếu cần

Ví dụ:

```json
{
  "id": "audio_a31f",
  "filename": "audio_a31f.mp3",
  "original_filename": "music.mp3",
  "duration": 120,
  "format": "mp3",
  "sample_rate": 44100,
  "size": 5242880,
  "status": "READY"
}
```

---

# 4. Trách nhiệm của Web

Web chỉ:

- Nhập Text
- Upload Audio
- Hiển thị danh sách Audio
- Chọn Audio
- Play
- Pause
- Stop
- Volume
- Hiển thị Metadata
- Hiển thị trạng thái ESP32

Web chỉ giao tiếp với Backend API.

Web KHÔNG được:

```text
Web → MQTT trực tiếp
Web → ESP32 trực tiếp
Web → Cloud Database trực tiếp
Web → Backend File System trực tiếp
```

---

# 5. Trách nhiệm Backend Python

Backend là trung tâm điều phối.

Backend chịu trách nhiệm:

- REST API
- Validate Input
- Nhận File Upload
- Lưu File Audio
- Text-to-Speech
- Trích xuất Metadata
- Cung cấp Audio HTTP Endpoint
- Ghi Metadata lên Cloud
- Publish MQTT Command
- Subscribe MQTT Status/Event/Error
- Quản lý trạng thái logic
- Xử lý Notification
- Log runtime

Backend là thành phần duy nhất được phép:

- truy cập Audio Storage
- ghi Cloud Database
- gửi MQTT Command
- gửi Push Notification

---

# 6. Trách nhiệm ESP32

ESP32 chịu trách nhiệm:

- WiFi
- MQTT
- Nhận Command
- HTTP Audio Streaming
- Decode Audio
- Output I2S
- Gửi Status
- Gửi Event
- Gửi Error

ESP32 KHÔNG:

- truy cập Cloud Database trực tiếp
- gửi Notification trực tiếp
- tạo TTS
- sửa Metadata
- nhận nguyên File Audio qua MQTT
- tải toàn bộ File Audio vào RAM trước khi phát

---

# 7. Audio Streaming

ESP32 bắt buộc phát Audio theo kiểu streaming.

```text
Backend Audio HTTP Endpoint
↓
ESP32 mở HTTP Connection
↓
Đọc Audio từng chunk
↓
Buffer nhỏ
↓
Decode
↓
PCM
↓
I2S
↓
Loa
```

Không làm:

```text
HTTP
↓
Download toàn bộ File
↓
RAM
↓
Play
```

Không dùng:

```cpp
malloc(fileSize);
```

cho File Audio.

Buffer nên cố định, ví dụ:

- 4 KB
- 8 KB
- 16 KB

---

# 8. MQTT Topic Convention

Format:

```text
esp32/{device_id}/{type}
```

Ví dụ:

```text
esp32/esp32_01/command
esp32/esp32_01/status
esp32/esp32_01/event
esp32/esp32_01/error
```

---

# 9. MQTT QoS và Retain

## Command

```text
Topic: esp32/{device_id}/command
QoS: 1
Retain: false
```

Không retain Command cũ.

## Status

```text
Topic: esp32/{device_id}/status
QoS: 1
Retain: true
```

## Event

```text
QoS: 1
Retain: false
```

## Error

```text
QoS: 1
Retain: false
```

---

# 10. MQTT Last Will and Testament — LWT

ESP32 bắt buộc cấu hình LWT.

Topic:

```text
esp32/{device_id}/status
```

Payload:

```json
{
  "device_id": "esp32_01",
  "status": "OFFLINE",
  "reason": "UNEXPECTED_DISCONNECT"
}
```

```text
QoS: 1
Retain: true
```

Nếu ESP32 mất điện, mất WiFi, crash hoặc reset bất thường, Mosquitto tự Publish OFFLINE.

Sau khi ESP32 connect thành công phải Publish:

```json
{
  "device_id": "esp32_01",
  "status": "ONLINE"
}
```

với retain=true.

---

# 11. Device Status

Chỉ dùng:

```text
ONLINE
OFFLINE
IDLE
BUFFERING
PLAYING
PAUSED
RECORDING
STOPPED
ERROR
```

---

# 12. Audio Status

Chỉ dùng:

```text
PROCESSING
READY
PLAYING
COMPLETED
FAILED
```

---

# 13. MQTT Command Contract

## PLAY

```json
{
  "request_id": "req_a81f",
  "command": "PLAY",
  "audio_id": "audio_001",
  "audio_url": "http://backend:8000/api/v1/audio/audio_001/stream"
}
```

## STOP

```json
{
  "request_id": "req_a82f",
  "command": "STOP"
}
```

## PAUSE

```json
{
  "request_id": "req_a83f",
  "command": "PAUSE"
}
```

## RESUME

```json
{
  "request_id": "req_a83f_resume",
  "command": "RESUME"
}
```

RESUME chỉ hợp lệ khi ESP32 đang PAUSED và tiếp tục decoder hiện tại; PLAY vẫn là lệnh phát audio mới từ đầu.

## SET_VOLUME

```json
{
  "request_id": "req_a84f",
  "command": "SET_VOLUME",
  "volume": 70
}
```

## LIGHT

```json
{
  "request_id": "req_light_01",
  "command": "LIGHT",
  "state": "ON"
}
```

`state` chỉ nhận `ON` hoặc `OFF`; ESP32 phản hồi bằng event `LIGHT_CHANGED` với `light_state` tương ứng.

---

# 14. Command ACK

MQTT Publish thành công KHÔNG có nghĩa ESP32 đã thực hiện thành công.

```text
Web
↓
Backend
↓
MQTT Command
↓
ESP32
↓
ESP32 Validate
↓
ESP32 thực hiện
↓
ESP32 gửi Status / Event
↓
Backend
↓
Web cập nhật
```

Ví dụ:

```text
PLAY
↓
BUFFERING
↓
PLAYING
```

---

# 15. Command Ordering và Playback Concurrency

ESP32 KHÔNG sử dụng Command Priority Queue.

Command được xử lý theo thứ tự MQTT callback nhận được.

ESP32 chỉ có một Audio Playback Session tại một thời điểm.

## PLAY mới khi đang PLAY

PLAY mới thay thế PLAY hiện tại.

```text
PLAY A
↓
Playing A
↓
PLAY B
↓
Stop A
↓
Clear Buffer
↓
Start B
```

## STOP

STOP xử lý theo thứ tự nhận được.

Nếu đang PLAYING / BUFFERING / PAUSED:

1. dừng HTTP Stream
2. dừng Decoder
3. clear Audio Buffer
4. stop I2S
5. status → STOPPED

Nếu đang IDLE / STOPPED:

- không báo lỗi
- vẫn ACK `STOPPED`
- giữ cùng `request_id`

Ví dụ:

```json
{
  "request_id": "req_stop_01",
  "status": "STOPPED"
}
```

Backend có trách nhiệm hạn chế việc gửi nhiều command xung đột trong thời gian rất ngắn.

Không xây Command Queue dài ở version hiện tại.

ESP32 chỉ giữ:

```text
currentRequestId
currentCommand
currentAudioId
```

---

# 16. Request ID và Stale Response

Mọi Command phải có:

```text
request_id
```

ESP32 phản hồi phải giữ cùng request_id.

Backend phải bỏ qua response cũ nếu request_id không còn là request hiện tại.

Ví dụ:

```text
PLAY A → req_01
PLAY B → req_02
```

Nếu response của `req_01` tới sau `req_02`, Backend không được ghi đè trạng thái mới.

---

# 17. PLAY Stream Error

Nếu Audio HTTP Endpoint trả:

- 404
- 5xx
- connection failure
- timeout

ESP32 không được retry vô hạn.

Ví dụ:

```text
MAX_AUDIO_RETRY = 3
```

Nếu vẫn thất bại:

```text
status → ERROR
```

Publish:

```text
esp32/{device_id}/error
```

Payload ví dụ:

```json
{
  "request_id": "req_xxx",
  "error_code": "AUDIO_DOWNLOAD_FAILED",
  "message": "Unable to open audio stream"
}
```

---

# 18. MQTT chỉ truyền dữ liệu nhỏ

MQTT được truyền:

- JSON
- Filename
- URL
- Command
- Status
- Event
- Error
- Metadata nhỏ
- PCM recording chunks có kích thước giới hạn trên `esp32/{device_id}/audio/chunk/{recording_id}/{sequence}`

MQTT không truyền File Audio hoàn chỉnh. Riêng luồng ghi âm được phép truyền
PCM theo chunk để Backend ghép lại; MQTT vẫn không truyền WAV hoàn chỉnh.

Playback MQTT không truyền:

- nguyên File MP3
- nguyên File WAV
- binary audio lớn ngoài recording chunk contract

---

# 19. API Convention

Prefix:

```text
/api/v1
```

## Audio

```text
POST /api/v1/audio/upload
POST /api/v1/audio/tts
GET  /api/v1/audio
GET  /api/v1/audio/{audio_id}
DELETE /api/v1/audio/{audio_id}
GET  /api/v1/audio/{audio_id}/stream
GET  /api/v1/audio/{audio_id}/download
```

## Device

```text
GET  /api/v1/devices/{device_id}/status
POST /api/v1/devices/{device_id}/play
POST /api/v1/devices/{device_id}/pause
POST /api/v1/devices/{device_id}/resume
POST /api/v1/devices/{device_id}/stop
POST /api/v1/devices/{device_id}/volume
POST /api/v1/devices/{device_id}/record/start
POST /api/v1/devices/{device_id}/record/stop
```

---

# 20. API Response

Success:

```json
{
  "success": true,
  "data": {},
  "message": "OK"
}
```

Error:

```json
{
  "success": false,
  "error": {
    "code": "AUDIO_NOT_FOUND",
    "message": "Audio file not found"
  }
}
```

---

# 21. File Validation

Backend phải kiểm tra:

- Extension
- MIME Type
- File Size
- Audio Duration
- Filename
- File có decode được hay không

Format ban đầu:

```text
.mp3
.wav
```

Ví dụ:

```text
MAX_AUDIO_SIZE = 20 MB
```

---

# 22. File Naming

Không dùng Filename người dùng làm tên lưu vật lý chính.

User upload:

```text
My Song.mp3
```

Backend tạo:

```text
audio_a8f23.mp3
```

Cloud lưu:

```json
{
  "audio_id": "audio_a8f23",
  "filename": "audio_a8f23.mp3",
  "original_filename": "My Song.mp3"
}
```

---

# 23. Source of Truth

Backend:

- Source of Truth cho Business Logic

Backend Audio Storage:

- Source of Truth cho File Audio thật

Cloud Database:

- Source of Truth cho Metadata đã lưu

ESP32:

- Source of Truth cho trạng thái Hardware thực tế

Backend gửi PLAY không đồng nghĩa với PLAYING.

Chỉ khi ESP32 báo `PLAYING`, Backend mới xác nhận trạng thái thật.

---

# 24. Notification Flow

ESP32 không gửi Push Notification trực tiếp.

```text
ESP32
↓
MQTT Event / LWT
↓
Backend
↓
Cloud Notification Service
↓
Điện thoại
```

Ví dụ Event:

```text
PLAY_COMPLETED
AUDIO_FAILED
DEVICE_OFFLINE
```

---

# 25. Retry và Timeout

Không Retry vô hạn.

Ví dụ:

```text
Audio HTTP MAX_RETRY = 3
```

MQTT reconnect có thể tiếp tục nhưng phải dùng backoff:

```text
1s
2s
4s
8s
10s
```

Timeout ví dụ:

```text
HTTP Connect: 5 giây
Audio Read Timeout: 10 giây
Backend chờ Command ACK: 10 giây
```

Nếu không có ACK:

```text
COMMAND_TIMEOUT
```

---

# 26. Runtime Logging và Secret

Backend log tối thiểu:

```text
timestamp
device_id
request_id
action
audio_id
result
error
```

Không log:

- Password
- API Key
- MQTT Password
- Cloud Secret

Không hard-code Secret.

Dùng `.env`.

Ví dụ:

```env
MQTT_HOST=
MQTT_PORT=
MQTT_USERNAME=
MQTT_PASSWORD=

FIREBASE_PROJECT_ID=
AUDIO_STORAGE_PATH=
```

---

# 27. MQTT Permission

## Backend

Publish:

```text
esp32/+/command
```

Subscribe:

```text
esp32/+/status
esp32/+/event
esp32/+/error
esp32/+/audio/#
```

## ESP32

Subscribe:

```text
esp32/{device_id}/command
```

Publish:

```text
esp32/{device_id}/status
esp32/{device_id}/event
esp32/{device_id}/error
esp32/{device_id}/audio/start
esp32/{device_id}/audio/chunk/{recording_id}/{sequence}
esp32/{device_id}/audio/end
```

ESP32 không được Publish vào command topic.

Web không có MQTT Credential.

---

# 28. Backend Structure

```text
backend/
│
├── app/
│   ├── routes/
│   │   ├── audio_routes.py
│   │   └── device_routes.py
│   │
│   ├── services/
│   │   ├── audio_service.py
│   │   ├── audio_stream_service.py
│   │   ├── tts_service.py
│   │   ├── metadata_service.py
│   │   ├── mqtt_service.py
│   │   ├── cloud_service.py
│   │   └── notification_service.py
│   │
│   ├── models/
│   ├── utils/
│   └── config/
│
├── storage/
│   └── audio/
│
├── tests/
├── LOG.md
├── TASK.md
├── PROJECT_RULES.md
├── AGENT_WORKFLOW.md
├── .env
└── requirements.txt
```

---

# 29. ESP32 Structure

```text
esp32/
│
├── main.ino
├── config.h
│
├── wifi_manager.cpp
├── wifi_manager.h
│
├── mqtt_manager.cpp
├── mqtt_manager.h
│
├── audio_stream.cpp
├── audio_stream.h
│
├── audio_player.cpp
├── audio_player.h
│
├── command_handler.cpp
├── command_handler.h
│
├── status_manager.cpp
└── status_manager.h
```

`main.ino` chỉ dùng cho:

- setup()
- loop()
- orchestration cơ bản

---

# 30. Naming Convention

## Python

```text
snake_case
```

Ví dụ:

```text
audio_service.py
extract_metadata()
audio_file
```

## JavaScript

```text
camelCase
```

Class:

```text
PascalCase
```

## ESP32

Function / Variable:

```text
camelCase
```

Constant:

```text
UPPER_SNAKE_CASE
```

---

# 31. Quyền giữa các Layer

## Web

Được:

```text
Web → Backend API
```

Không được:

```text
Web → MQTT
Web → ESP32
Web → Cloud DB
Web → File System
```

## Backend

Được:

```text
Backend → MQTT
Backend → Cloud
Backend → Audio Storage
Backend → Notification Service
```

## ESP32

Được:

```text
ESP32 → MQTT
ESP32 → Backend Audio HTTP Endpoint
```

Không được:

```text
ESP32 → Cloud Database
ESP32 → Web trực tiếp
ESP32 → Backend Admin API
```

---

# 32. Mandatory Rules

1. File Audio thật chỉ nằm tại Backend.
2. Cloud Service là service ngoài Backend.
3. Một Cloud Service có thể đảm nhiệm Database + Notification.
4. Cloud Database chỉ lưu Filename + Metadata + Status.
5. MQTT không truyền File Audio.
6. ESP32 phát Audio bằng Streaming.
7. Không tải toàn bộ Audio vào ESP32 RAM.
8. Command dùng QoS 1 + retain=false.
9. Status dùng QoS 1 + retain=true.
10. ESP32 bắt buộc dùng MQTT LWT.
11. ESP32 chỉ có một Playback Session tại một thời điểm.
12. Không dùng Command Priority Queue ở ESP32.
13. Command xử lý theo thứ tự nhận.
14. PLAY mới thay PLAY hiện tại.
15. STOP khi IDLE vẫn ACK STOPPED.
16. PLAY gặp 404/5xx/timeout phải fail có kiểm soát, không retry vô hạn.
17. Mọi Command có request_id.
18. Backend bỏ qua stale response.
19. Backend chỉ cập nhật trạng thái thật sau Status từ ESP32.
20. Web không giao tiếp trực tiếp MQTT / ESP32 / Cloud.
21. Secret không hard-code.
22. Network operation phải có Timeout.
23. Retry phải có giới hạn hoặc backoff.
24. Không over-engineer version đầu.

---

# 33. Luồng ghi âm INMP441 → Web

```text
[Người nói vào Micro INMP441]
          ↓ I2S RX
       [ESP32]
          ↓ START_RECORDING
[JSON start marker qua MQTT]
          ↓
[PCM s16le chunks qua MQTT]
  esp32/{device_id}/audio/chunk/{recording_id}/{sequence}
          ↓
[Mosquitto MQTT Broker]
          ↓
[Backend Python nhận và kiểm tra thứ tự chunk]
          ├── Ghép PCM vào file tạm
          ├── Đóng gói Header WAV: 16 kHz / Mono / 16-bit
          ├── Lưu file thật: backend/storage/audio/rec_xxx.wav
          └── Lưu metadata: backend/storage/metadata.json
          ↓
[GET /api/v1/audio cập nhật danh sách]
          ↓
[Web Dashboard]
          ├── phát lại bằng <audio controls>
          └── tải về qua /api/v1/audio/{audio_id}/download
```

- ESP32 gửi `START_RECORDING` và `STOP_RECORDING` qua command topic; ghi tự dừng theo thời lượng giới hạn.
- MQTT chunk là raw PCM có sequence bắt đầu từ `0`; Backend bỏ qua duplicate cũ và từ chối chunk đến sai thứ tự.
- Backend là source of truth cho WAV/metadata; Cloud nếu được cấu hình chỉ nhận metadata nhẹ.
- Device status bổ sung `RECORDING`; hoàn tất phát event `RECORDING_COMPLETED`.
