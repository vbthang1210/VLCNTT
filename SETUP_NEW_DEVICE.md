# Setup ESP32 Audio System trên máy mới

Hướng dẫn này dùng Windows PowerShell. Source hiện tại dùng Telegram Bot cho notification MVP; không cần Android Studio, Firebase hoặc FCM.

## 1. Chuẩn bị máy tính

Cài các thành phần sau:

- Python 3.11 hoặc mới hơn
- `uv`
- Node.js LTS
- Mosquitto MQTT nếu muốn chạy MQTT thật trên máy
- Arduino IDE/CLI và thư viện ESP32 nếu muốn nạp firmware

Kiểm tra tool:

```powershell
python --version
uv --version
node --version
npm --version
mosquitto_pub -h 2>$null
arduino-cli version
```

Nếu máy chưa có `uv`, có thể cài bằng:

```powershell
python -m pip install uv
```

## 2. Lấy source

Giải nén source ZIP vào một thư mục, ví dụ:

```text
C:\Users\<user>\Downloads\esp32-audio-system
```

Mở PowerShell tại thư mục đó:

```powershell
cd C:\Users\<user>\Downloads\esp32-audio-system
```

Không copy các file credential từ máy cũ vào Git/source package.

## 3. Cài Backend dependency

`uv` sẽ tạo environment riêng cho Backend:

```powershell
uv run --directory backend pytest -q
```

Expected hiện tại:

```text
83 passed, 2 skipped
```

Hai test skipped là MQTT authenticated integration test khi chưa có broker credentials.

## 4. Tạo Telegram Bot

Trong ứng dụng Telegram:

1. Tìm `@BotFather`.
2. Gửi `/newbot`.
3. Đặt tên bot.
4. Lưu bot token ở máy local.
5. Mở chat với bot mới tạo và gửi `/start`.

Không gửi bot token vào chat hoặc commit vào Git.

## 5. Lấy Telegram Chat ID

Trong PowerShell, đặt token local:

```powershell
$env:TELEGRAM_BOT_TOKEN = "BOT_TOKEN_CUA_BAN"
```

Gọi Telegram API:

```powershell
$updates = Invoke-RestMethod `
  -Uri "https://api.telegram.org/bot$env:TELEGRAM_BOT_TOKEN/getUpdates"

($updates.result | Select-Object -Last 1).message.chat.id
```

Lưu Chat ID local. Nếu dùng group Telegram, hãy add bot vào group và gửi một tin nhắn; Chat ID group thường là số âm.

## 6. Test Telegram trước khi chạy Backend

```powershell
$env:TELEGRAM_CHAT_ID = "CHAT_ID_CUA_BAN"

$body = @{
  chat_id = $env:TELEGRAM_CHAT_ID
  text = "TEST ESP32 notification"
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri "https://api.telegram.org/bot$env:TELEGRAM_BOT_TOKEN/sendMessage" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

Expected response có:

```json
{
  "ok": true
}
```

Nếu bước này chưa gửi được thì chưa cần chạy Backend. Kiểm tra bot token, Chat ID và việc đã gửi `/start` cho bot.

## 7. Chạy Backend + Telegram + MQTT

Nếu chỉ test API/Telegram, có thể đặt `MQTT_ENABLED=false`. Nếu muốn nhận event từ Mosquitto/ESP32, dùng `true`.

Mở PowerShell thứ nhất và giữ nguyên cửa sổ đó:

```powershell
cd C:\Users\<user>\Downloads\esp32-audio-system

$env:HOST = "127.0.0.1"
$env:PORT = "8000"
$env:PUBLIC_BASE_URL = "http://127.0.0.1:8000"
$env:MQTT_ENABLED = "true"
$env:MQTT_HOST = "127.0.0.1"
$env:MQTT_PORT = "1883"
$env:MQTT_USERNAME = ""
$env:MQTT_PASSWORD = ""

$env:NOTIFICATION_PROVIDER = "telegram"
$env:TELEGRAM_BOT_TOKEN = "BOT_TOKEN_CUA_BAN"
$env:TELEGRAM_CHAT_ID = "CHAT_ID_CUA_BAN"

uv run --directory backend python run.py
```

Không đóng PowerShell này; các biến `$env:` chỉ có hiệu lực trong process hiện tại.

Backend health:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

## 8. Chạy Frontend

Mở PowerShell thứ hai:

```powershell
cd C:\Users\<user>\Downloads\esp32-audio-system
npm --prefix frontend start
```

Mở trình duyệt:

```text
http://127.0.0.1:3000
```

Frontend chỉ gọi Backend REST; Telegram notification do Backend gửi, không cần frontend mở để Telegram nhận event.

## 9. Firestore cloud metadata (tùy chọn)

Nếu muốn dữ liệu metadata từ Firestore xuất hiện trên Web Dashboard, đặt các biến này trong cùng PowerShell chạy Backend:

```powershell
$env:CLOUD_PROVIDER = "firestore"
$env:CLOUD_PROJECT_ID = "FIREBASE_PROJECT_ID_CUA_BAN"
$env:CLOUD_ACCESS_TOKEN = (gcloud auth application-default print-access-token).Trim()
$env:CLOUD_COLLECTION = "audio_metadata"
```

Web gọi `GET /api/v1/audio`; Backend sẽ đọc Firestore rồi merge với file audio local. Firestore chỉ chứa metadata, không chứa WAV/MP3 trong pipeline này. Nếu không cấu hình Cloud, Web vẫn hiển thị dữ liệu local.

Nếu Firestore request bị lỗi quyền/token, Backend giữ local list và ghi warning; không được coi đó là Cloud `PASS`.

## 10. Chạy Mosquitto

Nếu Mosquitto chạy foreground:

```powershell
mosquitto -v
```

Nếu cài dạng Windows service, kiểm tra:

```powershell
Get-Service mosquitto
```

Nếu broker dùng authentication, không để anonymous trong môi trường thật. Set đúng `MQTT_USERNAME` và `MQTT_PASSWORD` ở PowerShell chạy Backend và firmware local config.

## 11. Test MQTT → Backend → Telegram

Nếu đã cài `mosquitto_pub`:

```powershell
mosquitto_pub `
  -h 127.0.0.1 `
  -p 1883 `
  -t esp32/esp32_01/event `
  -q 1 `
  -m '{"device_id":"esp32_01","event":"TEST_NOTIFICATION","request_id":"req_test"}'
```

Expected Telegram message:

```text
🔔 ESP32 event: TEST_NOTIFICATION
esp32_01: TEST_NOTIFICATION
```

Nếu broker có authentication:

```powershell
mosquitto_pub `
  -h 127.0.0.1 `
  -p 1883 `
  -u $env:MQTT_USERNAME `
  -P $env:MQTT_PASSWORD `
  -t esp32/esp32_01/event `
  -q 1 `
  -m '{"device_id":"esp32_01","event":"TEST_NOTIFICATION","request_id":"req_test"}'
```

## 12. Chạy ESP32 thật (tùy chọn)

### Backend LAN

Điện thoại/ESP32 không thể kết nối `127.0.0.1` của máy tính. Chạy Backend với:

```powershell
$env:HOST = "0.0.0.0"
$env:PUBLIC_BASE_URL = "http://IP_LAN_MAY_TINH:8000"
```

Lấy IP LAN máy tính:

```powershell
ipconfig
```

Mở port 8000 trên Windows Firewall Private Network nếu cần.

### Firmware local config

Copy template:

```text
main/config.local.h.example
→ main/config.local.h
```

Điền:

- WiFi SSID/password
- `MQTT_HOST` = IP LAN máy tính, không dùng `127.0.0.1`
- `MQTT_USERNAME` cho ESP32 phải là user có quyền đọc command/ghi status; không dùng user Backend.
- MQTT username/password nếu broker bật auth
- device ID
- chân I2S/DAC/INMP441 nếu wiring khác

`main/config.local.h` bị ignore và không được commit.

### Compile firmware

```powershell
arduino-cli compile `
  --clean `
  --warnings all `
  --fqbn esp32:esp32:esp32 `
  main
```

Compile PASS không thay thế kiểm thử WiFi/MQTT/I2S/loa thật.

## 13. TTS miễn phí

Trong cùng PowerShell chạy Backend:

```powershell
$env:TTS_PROVIDER = "edge"
$env:TTS_VOICE = "vi-VN-HoaiMyNeural"
```

Edge TTS cần Internet nhưng không cần API key.

## 14. AI keyword tùy chọn

Không cần cài nếu chỉ chạy MVP Backend/Telegram:

```powershell
cd C:\Users\<user>\Downloads\esp32-audio-system\backend
uv pip install -r requirements-ai.txt
```

Training cần dataset thật:

```powershell
python training/preprocess_dataset.py --augmentations 2 --seed 42
python training/train.py --epochs 30
```

Không đưa dataset/checkpoint vào source package.

## 15. Verification cuối

Từ root project:

```powershell
npm run check
```

Status hiện tại:

```text
PASS — host test suite
PASS — Telegram fake HTTP contract
PASS — firmware compile khi Arduino CLI/libraries có sẵn
2 skipped — authenticated MQTT credentials chưa có
NOT VERIFIED — Telegram Bot delivery thật nếu chưa cấu hình token/chat ID
NOT VERIFIED — ESP32 hardware/LAN/I2S/speaker runtime
```

## 16. Không đưa vào Git/source package

Không commit hoặc gửi:

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID nếu muốn giữ riêng
main/config.local.h
.env thật
*.pyc
backend/storage/audio/*.wav
backend/storage/audio/*.mp3
backend/storage/models/*.pt
```
