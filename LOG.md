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

### 2026-08-18 - Voice AI command pipeline wiring

- Đã làm:
  - Added `VoiceCommandService` to convert accepted AI keyword predictions into device LIGHT commands.
  - Mapping is explicit: `bat -> LIGHT ON`, `tat -> LIGHT OFF`; `unknown`, `silence`, and low-confidence predictions do not publish commands.
  - Wired completed ESP32 audio sessions so the saved WAV is passed to AI inference after `audio/end`.
  - MQTT publish success initially registered the AI request as the device current request; this behavior was corrected in the next task because LIGHT acknowledgement is event-based and must not interfere with audio request state.
  - AI/MQTT downstream failures do not invalidate or delete a WAV that was already received and saved successfully.
  - Added unit tests for ON/OFF mapping, no-action labels, low confidence, MQTT publish failure, and the completed-audio callback.

- File đã sửa/thêm:
  - `backend/app/services/voice_command_service.py`
  - `backend/app/services/audio_stream_service.py`
  - `backend/app/services/__init__.py`
  - `backend/app/__init__.py`
  - `backend/tests/test_voice_command_service.py`
  - `backend/tests/test_audio_completed_hook.py`

- Test:
  - Tests were added but could not be executed inside the assistant runtime because direct network access to clone the updated GitHub branch was unavailable.
  - Required local verification: `python -m pytest tests/test_ai.py tests/test_voice_command_service.py tests/test_audio_completed_hook.py tests/test_mqtt_service.py -q`.

- Còn thiếu / lưu ý:
  - A valid `backend/storage/models/keyword_cnn.pt` is still required for real inference.
  - ESP32 microphone capture and MQTT `audio/start`, `audio/data`, `audio/end` publishing are still not implemented on the physical firmware path.
  - Physical voice -> AI -> MQTT -> LED end-to-end remains NOT VERIFIED.

### 2026-08-18 - LIGHT acknowledgement and device light state

- Đã làm:
  - Added a development `LED_PIN` default in `main/config.h` and removed the duplicate pin macro from `led_manager.h`.
  - `main.ino` now uses `LedManager` for the LIGHT command path.
  - LIGHT commands no longer publish synthetic device statuses such as `LIGHT_ON` or `LIGHT_OFF`; ESP32 publishes `LIGHT_CHANGED` events with explicit `light_state` instead.
  - Backend `DeviceState` now tracks `light_state` independently from audio/device `status`.
  - Backend event ingestion preserves `request_id`, `audio_id`, and validates/persists `light_state`.
  - Voice AI LIGHT commands no longer replace the device's current PLAY/STOP request, avoiding stale-response interference with audio playback.
  - Aligned Python MQTT dependency with the code's Paho callback API v2 by requiring `paho-mqtt>=2.0,<3.0`.

- File đã sửa:
  - `main/config.h`
  - `main/led_manager.h`
  - `main/main.ino`
  - `backend/app/mqtt_service.py`
  - `backend/app/services/voice_command_service.py`
  - `backend/app/__init__.py`
  - `backend/requirements.txt`
  - `backend/pyproject.toml`
  - `backend/tests/test_mqtt_service.py`
  - `backend/tests/test_voice_command_service.py`

- Test:
  - Added a regression test proving `LIGHT_CHANGED` updates `light_state` without overwriting a `PLAYING` device status/current playback request.
  - Runtime tests and Arduino compile remain to be executed on the user's Windows/Arduino environment.

- Còn thiếu / lưu ý:
  - `LED_PIN=2` is only a development default; replace it with the real lamp/relay GPIO if hardware wiring differs.
  - Physical LIGHT command acknowledgement remains NOT VERIFIED until the ESP32 is flashed and connected to Mosquitto.
  - Next implementation step: INMP441 capture -> MQTT `audio/start`, `audio/data`, `audio/end`.
