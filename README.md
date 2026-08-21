# ESP32 Audio System

Development MVP for the architecture described in `PROJECT_RULES.md`.

## Current layout

```text
main/                         Arduino sketch
backend/                      Flask API, storage, MQTT bridge, tests
frontend/                     Node.js static web UI/server
docs/PROJECT_TASKS.md         implementation status
SETUP_NEW_DEVICE.md           full Windows setup and Telegram runbook
ARCHITECTURE_LOG.md           development decisions
TASK.md                       current task checkpoint
LOG.md                        append-only task log
```

## Development defaults

See `ARCHITECTURE_LOG.md`. The default local stack uses:

- Backend: `http://127.0.0.1:8000`
- Frontend: `http://127.0.0.1:3000`
- MQTT: `127.0.0.1:1883`, anonymous
- Device ID: `esp32_01`

The ESP32 cannot connect to a loopback broker. For hardware, copy `main/config.local.h.example` to `main/config.local.h`, fill the local WiFi/MQTT values, and configure Mosquitto/firewall accordingly. `config.local.h` is ignored and must not be committed.

## Backend

```bash
cd backend
uv venv .venv --python python
uv pip install -r requirements.txt
uv run python run.py
```

Useful environment variables:

```text
MQTT_ENABLED=true|false
MQTT_HOST=127.0.0.1
MQTT_PORT=1883
MQTT_USERNAME=
MQTT_PASSWORD=
DEVICE_ID=esp32_01
PUBLIC_BASE_URL=http://127.0.0.1:8000
AUDIO_STORAGE_PATH=storage/audio
METADATA_PATH=storage/metadata.json
RECORDING_DEFAULT_SECONDS=5
RECORDING_MAX_SECONDS=60
RECORDING_SESSION_TIMEOUT_SECONDS=15
```

For free TTS, set `TTS_PROVIDER=edge` and use an Edge voice name such as
`vi-VN-HoaiMyNeural`. For ElevenLabs, `TTS_PROVIDER=elevenlabs` uses `TTS_VOICE` as the ElevenLabs Voice ID,
`TTS_API_KEY` as the `xi-api-key`, and `TTS_API_URL=https://api.elevenlabs.io/v1/text-to-speech`.

## Optional keyword AI and training

The `bat`/`tat` keyword model is optional. Install its dependencies separately:

```bash
cd backend
uv pip install -r requirements-ai.txt
cd ..
python backend/training/preprocess_dataset.py --augmentations 2 --seed 42
python backend/training/train.py --epochs 30
```

Training uses `dataset/processed/` by default after preprocessing; pass `--dataset` to override it.

Place raw one-second WAV samples in `dataset/raw/{bat,tat,unknown,silence}/`.
The checkpoint is written to `backend/storage/models/keyword_cnn.pt`; without Torch or a checkpoint, Backend remains healthy with `ai_ready=false`.

Run tests:

```bash
python -m pytest -q
```

## Frontend

```bash
cd frontend
npm start
```

Open `http://127.0.0.1:3000`.

## Telegram notification

Để nhận thông báo trực tiếp trong ứng dụng Telegram, tạo bot bằng `@BotFather`, gửi `/start` cho bot rồi cấu hình local:

```text
NOTIFICATION_PROVIDER=telegram
TELEGRAM_BOT_TOKEN=<bot-token>
TELEGRAM_CHAT_ID=<chat-id>
```

Backend gửi MQTT event/error/OFFLINE tới Telegram Bot API. Không cần Android app hoặc Firebase. Không gửi bot token vào chat và không commit token.

Lấy chat ID local bằng Telegram Bot API sau khi gửi `/start` cho bot:

```powershell
$env:TELEGRAM_BOT_TOKEN = "BOT_TOKEN_CUA_BAN"
(Invoke-RestMethod "https://api.telegram.org/bot$env:TELEGRAM_BOT_TOKEN/getUpdates").result[-1].message.chat.id
```

## Firestore cloud metadata (optional)

When configured, Backend reads Firestore `audio_metadata` documents and merges them into `GET /api/v1/audio` for the Web Dashboard. Audio bytes remain local in Backend storage; a Cloud-only record is metadata-only until its audio file is available locally.

```text
CLOUD_PROVIDER=firestore
CLOUD_PROJECT_ID=<firebase-project-id>
CLOUD_ACCESS_TOKEN=<local-oauth-access-token>
CLOUD_COLLECTION=audio_metadata
```

If Firestore is not configured or temporarily unavailable, the Web Dashboard falls back to Backend-local metadata instead of returning an empty list.

## Firmware

Open `main/main.ino` in Arduino IDE or compile directly:

```bash
arduino-cli compile --fqbn esp32:esp32:esp32 main
```

Install/select Arduino-ESP32 Core and the libraries listed in `main/README.md` or the Arduino sketchbook. The tracked `main/config.h` contains safe defaults; use the ignored `main/config.local.h` override before hardware use.

## Verification status

Host compile/API tests can be run locally. ESP32 upload, WiFi, MQTT-over-LAN, decoder, I2S and speaker behavior require the target hardware and are not claimed as verified without evidence.
