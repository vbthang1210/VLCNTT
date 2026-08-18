# Project Log

### 2026-08-15 - Development MVP implementation started

- Đã làm:
  - Ghi development defaults trong `ARCHITECTURE_LOG.md`.
  - Giữ các contract MQTT/architecture hiện có làm source of truth.
  - Bắt đầu triển khai Backend, Frontend và firmware MVP.

- Test:
  - IN PROGRESS tại thời điểm entry này.

- Còn thiếu / lưu ý:
  - Hardware ESP32, DAC/I2S, TTS provider và Cloud credentials chưa có.

### 2026-08-15 - Host MVP, MQTT bridge and firmware compile

- Đã làm:
  - Backend Flask API: audio upload/list/get/stream, device commands, status/error/event state handling.
  - Backend MQTT bridge theo canonical per-device topics, QoS 1, stale-response filtering.
  - Frontend Node static server và API-only control UI.
  - ESP32 MQTT manager, LWT, command validation, bounded stream buffer, MP3/WAV decoder boundary, I2S lifecycle and playback events.
  - Added explicit TTS, Cloud metadata and notification provider boundaries that fail closed without credentials.

- File đã sửa/thêm:
  - `backend/`
  - `frontend/`
  - `main/`
  - `ARCHITECTURE_LOG.md`
  - `README.md`
  - `TASK.md`
  - `docs/PROJECT_TASKS.md`

- Test:
  - PASS — `uv run pytest -q`: 11 passed.
  - PASS — `npm run check`.
  - PASS — `python -m compileall -q app tests`.
  - PASS — Arduino compile, exit code 0; 1 dependency warning in ESP8266Audio PDM source.
  - PASS — local Mosquitto/Paho QoS 1 round-trip.
  - PASS — Backend HTTP health, audio upload/stream and PLAY command smoke.
  - PASS — Frontend HTTP 200 for `/` and `/app.js`.
  - PARTIAL — no physical ESP32, DAC/I2S, TTS provider, Cloud or push notification verification.

- Còn thiếu / lưu ý:
  - Mosquitto is loopback-only; hardware requires LAN broker bind/firewall and replacing `MQTT_HOST`.
  - WiFi credentials are placeholders and must be provided locally.
  - I2S pins are development defaults and require actual DAC confirmation.
  - Full browser interaction and hardware end-to-end remain NOT VERIFIED.

### 2026-08-15 - Final host verification checkpoint

- Test:
  - PASS — 11 Backend tests.
  - PASS — Node syntax checks.
  - PASS — Arduino compile with ESP32 Core 3.3.11 and installed libraries.
  - PASS — local Mosquitto listener and retained status observation.
  - PASS — Backend status update from broker status payload.
  - PASS — live Backend `POST /api/v1/devices/esp32_01/stop` returned 202 and a Mosquitto subscriber captured `esp32/esp32_01/command` with `request_id=req_capture_stop_01` and `command=STOP`.
  - PASS — Frontend HTTP smoke returned 200 for `/` and `/app.js`.

- Còn thiếu / lưu ý:
  - Physical ESP32/DAC/I2S and browser interaction remain NOT VERIFIED.
  - TTS, Cloud database and Push Notification providers remain unconfigured.
  - Temporary test artifacts were removed from `backend/storage` and `backend/test_artifacts` after verification.

### 2026-08-15 - Final source cleanup

- Đã làm:
  - Removed temporary generated audio and MQTT capture artifacts from runtime storage.
  - Kept only source, tests, `.env.example`, and an empty `storage/audio` directory.
  - Updated `TASK.md` to `PARTIAL` rather than claiming full end-to-end completion.

- Test:
  - PASS — final host checks before cleanup: 11 Backend tests, Node check, Python compileall, Arduino compile, HTTP health and frontend smoke.

- Còn thiếu / lưu ý:
  - The project is host-MVP complete, not hardware/E2E complete.

### 2026-08-15 - Hermes verification recipe

- Đã làm:
  - Added root `package.json`, `verify-run.py`, and one-shot `verify-start.js` so the composite project is discoverable by `hermes verify`.
  - Kept the readiness server separate from the real Frontend server; it only proves the root recipe can boot and respond, then exits cleanly on Windows.

- Test:
  - PASS — `hermes verify --json`.
  - Bootstrap: `npm install`.
  - Test: root `npm run check`, including Node syntax, 11 Python tests, and Python compileall.
  - Readiness: `http://127.0.0.1:8000/` returned HTTP 200.
  - Final process cleanup: no verify process remains on port 8000.

- Còn thiếu / lưu ý:
  - Hermes recipe does not replace the separate Arduino compile command; Arduino compile remains recorded and passed independently.
  - Physical ESP32/DAC/I2S, real TTS, Cloud, push notification and browser interaction remain NOT VERIFIED.

### 2026-08-15 - Fresh verification after verify-start change

- Test:
  - PASS — `npm run check`: frontend syntax, 11 Backend tests, Python compileall.
  - PASS — `hermes verify --json`: npm bootstrap, root test command, readiness HTTP 200 at `http://127.0.0.1:8000/`.
  - PASS — Arduino compile with ESP32 Core 3.3.11; exit code 0, 1090740 bytes (83%), 49936 bytes global (15%).
  - Warning — dependency warning from ESP8266Audio `AudioOutputPDM.cpp`; no project-source compile failure.

- Còn thiếu / lưu ý:
  - No ESP32 board/DAC/I2S runtime evidence. TTS/Cloud/notification providers remain unconfigured.

### 2026-08-15 - Fresh verification rerun after system stale warning

- Test:
  - PASS — `npm run check`, exit code 0; 11 Backend tests passed.
  - PASS — `hermes verify --json`, exit code 0; bootstrap passed, test passed, readiness HTTP 200.
  - PASS — verify process cleanup; port 8000 is not LISTENING, only TIME_WAIT remains.

- Còn thiếu / lưu ý:
  - Frontend development server remains on port 3000 by design.
  - Hardware/provider limitations are unchanged.

### 2026-08-15 - Provider adapters implemented

- Đã làm:
  - Implemented an environment-configured OpenAI-compatible TTS adapter in `backend/app/services/tts_service.py`.
  - TTS provider bytes are persisted through Backend-owned `AudioRepository`; the `/api/v1/audio/tts` route also sends light metadata through the Cloud boundary.
  - Implemented Firestore REST adapters for audio metadata and device status in `backend/app/services/cloud_service.py`.
  - Upload metadata and MQTT device status now call the Cloud service; missing provider configuration remains fail-closed/local-only.
  - Implemented FCM HTTP v1 notification adapter in `backend/app/services/notification_service.py`.
  - MQTT events, error states, and OFFLINE status now dispatch notifications without blocking state ingestion.
  - Added environment names to `backend/.env.example` and updated `TASK.md` plus `docs/PROJECT_TASKS.md` with exact verification status.

- Test:
  - PASS — provider targeted tests: 12 passed.
  - PASS — full Backend suite: 23 passed in 4.56s.
  - PASS — `npm run check`: Node syntax, full Backend tests, and compile checks passed.
  - PASS — fake-HTTP requests verified endpoint, method, timeout, authorization header, and payload field filtering.

- Còn thiếu / lưu ý:
  - NOT VERIFIED — real TTS call: no provider endpoint/API key/model/voice configured.
  - NOT VERIFIED — real Firestore write: no project/token configured.
  - NOT VERIFIED — real FCM delivery: no project/access token/device token configured.
  - No secrets were written to the repository.
  - Physical ESP32/DAC/I2S and browser interaction remain NOT VERIFIED.

- Scope stopped after provider-adapter implementation and host verification; hardware and real external-provider smoke tests require user-supplied configuration.

### 2026-08-18 03:21 - Add INMP441 recording flow

- Đã làm:
  - Added `PcmRecordingService` to receive ordered raw PCM MQTT chunks, assemble a temporary stream, write a 16 kHz mono 16-bit WAV, and persist `rec_xxx.wav` plus `backend/storage/metadata.json`.
  - Added Backend subscriptions for `esp32/+/audio/#`, `START_RECORDING`/`STOP_RECORDING` command APIs, `RECORDING` device state, and the download endpoint.
  - Added ESP32 I2S1 INMP441 capture, 512-sample PCM chunk publishing, start/end markers, and bounded recording duration.
  - Added Dashboard recording controls, live audio preview, per-record `<audio controls>`, and download links.
  - Updated `PROJECT_RULES.md`, `FLOW.md`, `ARCHITECTURE_LOG.md`, `TASK.md`, and `docs/PROJECT_TASKS.md` with the new contract and explicit verification boundaries.
  - Fixed the one-shot `verify-start.js` readiness recipe to close HTTP connections cleanly.

- File đã sửa/thêm:
  - `backend/app/services/recording_service.py`
  - `backend/app/storage.py`
  - `backend/app/mqtt_service.py`
  - `backend/app/routes/audio_routes.py`
  - `backend/app/routes/device_routes.py`
  - `backend/tests/test_recording.py`
  - `backend/tests/test_mqtt_integration.py`
  - `main/microphone_recorder.cpp`, `main/microphone_recorder.h`
  - `main/mqtt_manager.cpp`, `main/mqtt_manager.h`, `main/main.ino`, `main/config.h`
  - `frontend/public/index.html`, `frontend/public/app.js`, `frontend/public/style.css`

- Test:
  - PASS — `npm run check`: 27 Backend tests, Node syntax, Python compile checks.
  - PASS — local Mosquitto integration: 2 tests, including raw PCM start/chunk/end → WAV persistence.
  - PASS — `hermes verify --json`: bootstrap, test, readiness HTTP 200, and cleanup.
  - PASS — Arduino CLI 1.5.0 / ESP32 Core 3.3.11 compile: 1,106,800 bytes (84%), 53,384 bytes global (16%).
  - PASS — live Backend/browser smoke: generated recording listed in Dashboard; stream returned `audio/wav`; WAV measured 16,000 Hz, mono, 16-bit, 800 frames; download returned `attachment`.

- Còn thiếu / lưu ý:
  - NOT VERIFIED — physical ESP32 + INMP441 capture, WiFi/MQTT-over-LAN, microphone signal quality, and speaker/browser E2E with hardware.
  - Warning — legacy ESP32 I2S API deprecation and pre-existing ESP8266Audio narrowing warning; compile still exited 0.
  - Runtime smoke artifact `rec_ui_f0a659.wav` and its metadata were removed after verification; no secrets were written.
