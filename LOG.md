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

### 2026-08-18 12:10 - Reliability review fixes

- Đã sửa:
  - Firmware oversized-command error now serializes `deviceId_`; `SET_VOLUME` emits `VOLUME_CHANGED` event without forcing `IDLE`.
  - Playback and microphone recording are mutually exclusive; `START_RECORDING` interrupts playback, `PLAY` finishes recording first, and `STOP` stops both. Removed fixed `delay(10)` from the main loop.
  - Added recording-session expiry timers with `RECORDING_SESSION_TIMEOUT_SECONDS=15`; stale `.pcm` files are removed on service startup.
  - Added atomic local audio DELETE (file + metadata), wired `AudioService`/`AudioStreamService` into routes, and removed unused `MetadataService` stub.
  - Upload now returns local `201` with `cloud_synced=false` when Cloud metadata sync fails after local persistence.
  - Frontend Backend URL follows the serving hostname, recording UI has countdown, and every record has a delete action.
  - Added firmware/frontend contract regression tests and included the frontend contract test in `verify-run.py`.

- Verification:
  - PASS — RED regression run observed all 9 new targeted failures before implementation.
  - PASS — `npm run check`: 36 tests, Node syntax, frontend contract, Python compile checks.
  - PASS — `hermes verify --json`: bootstrap, test, readiness HTTP 200.
  - PASS — Arduino compile: 1,107,268 bytes (84%), 53,384 bytes global (16%).
  - PASS — `git diff --check`.
  - NOT VERIFIED — Browser visual smoke was blocked by Chrome remote-debugging approval; HTTP health and Node contract checks passed.
  - NOT VERIFIED — physical ESP32/MQTT-over-LAN/microphone runtime. Test wrapper children still held ports 3000/8000 after wrapper termination; no forced `taskkill` was performed without user consent.

### 2026-08-18 15:14 - Fix ESP32 I2S driver conflict

- Evidence: physical Serial log showed `E (341) i2s(legacy): CONFLICT! The new i2s driver can't work along with the legacy i2s driver`, followed by abort/reboot when recording initialized.
- Root cause: `MicrophoneRecorder` used legacy `driver/i2s.h` APIs (`i2s_driver_install`, `i2s_read`) while `ESP8266Audio` playback uses the new ESP32 I2S driver.
- Fix: migrated microphone capture to `driver/i2s_std.h`/`i2s_common.h` new-channel APIs on `I2S_NUM_1`; playback remains on its separate I2S path.
- Verification:
  - PASS — regression contract: microphone includes `driver/i2s_std.h` and no longer calls legacy install/read APIs.
  - PASS — exact Arduino CLI compile with ESP32 Core 3.3.11: 1,095,032 bytes (83%), 53,352 bytes global (16%).
  - PASS — `npm run check`: 37 tests.
  - Warning — remaining compile warning originates from `ESP8266Audio` PDM narrowing, not the microphone driver.
  - NOT VERIFIED — re-upload and physical recording runtime; the new firmware must be flashed before retesting the board.

### 2026-08-18 17:30 - Diagnose short recording duration

- Evidence: `rec_ec7ca603.wav` contains exactly 52,736 frames at 16 kHz, giving 3.296 seconds; Backend persisted the received samples without truncation.
- Conclusion: the short recording occurs before WAV persistence, in the ESP32 command/stop/chunk path, not because Backend is slow.
- Added Serial diagnostics for requested duration, start duration in milliseconds, stop chunk/sample counts, I2S read failures, and MQTT chunk publish failures.
- PASS — exact firmware compile with ESP32 Core 3.3.11: 1,095,592 bytes (83%), 53,352 bytes global (16%).
- PASS — `npm run check`: 36 passed, 2 auth integration tests skipped without local credential env.
- Next hardware evidence required after re-upload: `RECORDING: command duration_s=...`, `started duration_ms=...`, and `stopping chunks=... samples=...`.

### 2026-08-18 18:41 - Fix MQTT capture backpressure

- Evidence: a 20-second command produced `stopping chunks=115 samples=58880`; serial showed MQTT disconnect and `MQTT chunk publish failed` during capture. WAV duration was 3.296–3.808 seconds, proving Backend persisted a short upstream stream rather than truncating it.
- Fix: audio PCM chunks now use non-blocking MQTT QoS0; start/end/commands remain QoS1. A pending chunk is retained and retried across reconnect, with a 10-second recovery bound and paused recording clock.
- Verification:
  - PASS — firmware regression contracts for pending chunk/recovery and non-blocking audio QoS.
  - PASS — exact Arduino compile: 1,096,060 bytes (83%), 53,368 bytes global (16%).
  - PASS — `npm run check`: 38 passed, 2 auth integration tests skipped without credential env.
  - NOT VERIFIED — new firmware upload/runtime 20-second sample count and microphone hiss source.

### 2026-08-19 02:53 - Port LED and optional keyword AI from origin/huy

- Đã làm:
  - Port `LedManager` vào `main/` with configurable `LED_PIN`, current MQTT `LIGHT ON/OFF` command, and `LIGHT_CHANGED` event; did not port Huy's `vlcntt` audio topics or overwrite current recording pipeline.
  - Added optional lazy AI runtime: missing Torch/checkpoint keeps Backend healthy and reports `ai_ready=false`.
  - Added `bat`/`tat` voice-command mapping to current `LIGHT` contract, with one-second recording-window guard and background executor so MQTT callbacks are not blocked.
  - Added optional training/model sources under `backend/training/`, `backend/model/`, and `backend/requirements-ai.txt`; scripts write `backend/storage/models/keyword_cnn.pt` after a real dataset is supplied.
  - Updated `PROJECT_RULES.md`, `TASK.md`, `README.md`, `ARCHITECTURE_LOG.md`, `docs/PROJECT_TASKS.md`, and `verify-run.py`.

- Verification:
  - PASS — AI/voice tests, LED firmware contract, Python compile for `app tests training model`.
  - PASS — exact Arduino compile: 1,096,680 bytes (83%), 53,368 bytes global (16%).
  - PASS — `npm run check`: 58 passed, 2 auth integration tests skipped without credential env.
  - NOT VERIFIED — physical LED output, a trained Torch checkpoint, keyword accuracy, and AI-to-ESP32 runtime E2E.
  - Security — `main/config.h` is tracked and already contains local hardware credentials in the baseline; this change adds no new secret, but credentials must be moved/rotated before publishing or committing a clean version.

### 2026-08-19 03:11 - Harden LED/AI/training port

- Đã sửa:
  - Reject malformed, non-finite, boolean, and out-of-window voice recording durations before inference.
  - Training defaults to `dataset/processed/` after preprocessing; `train.py --help` works without optional Torch installed.
  - Added integration coverage for INMP441 completion dispatch to the voice worker and unreadable AI checkpoint handling.
  - Removed unused training state and wrapped long lines for review readability.

- Verification:
  - PASS — `npm run check`: 63 passed, 2 auth integration tests skipped without credential env.
  - PASS — exact Arduino compile remains 1,096,680 bytes (83%), 53,368 bytes global (16%).
  - PASS — static scan found no dangerous execution, hardcoded secret assignment, or merge-conflict markers in new LED/AI/training files.
  - NOT VERIFIED — independent review result pending; physical LED output, trained-model accuracy, and AI-to-ESP32 hardware E2E remain unverified.

### 2026-08-19 03:16 - Remove duplicate runtime audio artifacts

- Evidence: `audio_5ea110b6.wav`, `audio_8c3033e0.wav`, `audio_47449ab8.wav`, and `audio_6c0ac2c3.wav` had the same SHA-256 as `rec_ca0a8cfd.wav` and were chained duplicate metadata entries.
- Đã xóa 4 duplicate WAV files, removed their metadata, and kept the original `rec_ca0a8cfd.wav`.
- Added root `.gitignore` for Python/build/runtime/training artifacts; existing tracked files are not silently ignored or rewritten.
- Verification: PASS — `npm run check`: 63 passed, 2 skipped; duplicate cleanup verified by file existence and metadata inspection.



### 2026-08-19 03:23 - Fix voice worker logger regression

- Root cause: `MqttService._process_voice_record()` called `logger.info/exception` without a module logger definition; the failure was hidden by the worker exception path.
- Fix: add `logging` import and `logger = logging.getLogger(__name__)` in `backend/app/mqtt_service.py`.
- Regression: `test_voice_worker_handles_prediction_result_without_logger_error` observed RED before the fix and GREEN after it.
- Verification: PASS — targeted tests 2 passed; full `npm run check` 64 passed, 2 skipped.

### 2026-08-19 03:41 - Resolve independent review findings

- Đã sửa:
  - `LIGHT_CHANGED` now serializes via ArduinoJson with JSON escaping and measured buffer bounds.
  - Voice executor has locked submit/stop/start lifecycle; shutdown waits for running inference and rejects submissions after stop.
  - Voice AI rejects missing duration, malformed/non-finite values, and windows outside 0.5–1.5 seconds.
  - Added `MODEL_DIR` and project-root preprocessing defaults; training/preprocess CLI paths no longer depend on current working directory.
  - Added regression tests for each finding, including the previously hidden voice-worker logger failure.

- Verification:
  - PASS — targeted RED/GREEN cycles for all listed findings.
  - PASS — `npm run check`: 70 passed, 2 skipped.
  - PASS — exact Arduino compile: 1,100,720 bytes (83%), 53,368 bytes global (16%).
  - NOT VERIFIED — final independent reviewer verdict, physical LED, Torch training/inference, and AI-to-ESP32 hardware E2E.

### 2026-08-19 03:48 - Harden all firmware JSON publishers

- Đã sửa:
  - Replaced remaining firmware `snprintf` JSON construction for state/error/event/recording payloads with one bounded ArduinoJson serializer.
  - Dynamic request, audio, and recording IDs are JSON-escaped; oversized payloads fall back to a static `PAYLOAD_TOO_LARGE` error without recursive formatting.
  - Added contract coverage requiring every publisher to use the bounded helper.

- Verification:
  - PASS — targeted firmware contract tests.
  - PASS — `npm run check`: 71 passed, 2 skipped.
  - PASS — Arduino compile: 1,102,168 bytes (84%), 53,368 bytes global (16%).
  - Warning — existing ESP8266Audio PDM narrowing conversion warning; compile still succeeds.
  - NOT VERIFIED — physical LED, Torch training/inference, and AI-to-ESP32 hardware E2E.

### 2026-08-19 03:56 - Harden MQTT manager JSON payloads

- Đã sửa `main/mqtt_manager.cpp` LWT/ONLINE, audio start/end, and oversized-command error payloads to use bounded ArduinoJson serialization; topic/QoS/binary PCM behavior is unchanged.
- Added MQTT manager contract coverage for the bounded JSON helper.
- Verification: PASS — `npm run check`: 72 passed, 2 skipped; Arduino compile `1,103,760 bytes (84%)`, RAM `53,368 bytes (16%)`.
- Warning: existing ESP8266Audio PDM narrowing conversion remains; compile exits 0.
- NOT VERIFIED — physical hardware/runtime and Torch model quality.

### 2026-08-19 04:02 - Validate MQTT topic identifiers

- Đã thêm validation identifier `[A-Za-z0-9_-]` và giới hạn độ dài trước khi build device/audio topics; kiểm tra `snprintf` không truncate.
- Không đổi topic, QoS, retain, hoặc binary PCM recording contract.
- Verification: PASS — targeted MQTT manager contract tests; `npm run check`: 73 passed, 2 skipped; Arduino compile `1,103,856 bytes (84%)`, RAM `53,368 bytes (16%)`.
- Warning: existing ESP8266Audio PDM narrowing conversion remains.

### 2026-08-19 04:08 - Final independent review gate

- Independent reviewer read current firmware/backend/training source and tests, but its final JSON verdict did not return after the tool timeout boundary and the run was stopped.
- Status: `NOT VERIFIED` for the independent-review approval gate; no new source changes were made after the final local checks.

### 2026-08-19 10:18 - Resolve final backend seam findings

- Đã sửa:
  - `VoiceCommandService` catches `OverflowError` for extreme duration input.
  - `MqttService.publish_command` validates device/request IDs, catches JSON/client exceptions, safely handles malformed publish results, and records the current request after success.
  - Backend package imports now work both from `backend/` and repository root; added regression coverage.
  - Firmware command ingress rejects unsafe/oversized request, recording, and audio IDs plus oversized audio URLs before side effects.

- Verification:
  - PASS — `npm run check`: 79 passed, 2 skipped.
  - PASS — exact Arduino compile: 1,104,084 bytes (84%), RAM 53,368 bytes (16%).
  - PASS — `git diff --check` and artifact cleanup.
  - NOT VERIFIED — final independent reviewer JSON; the reviewer read current seam files but exceeded the timeout boundary before returning.

### 2026-08-19 10:18 - Final seam hardening and review blocker

- Đã sửa các seam cuối:
  - `OverflowError` duration.
  - MQTT publish exception/result handling and current-request state.
  - Backend package-root imports.
  - Firmware command ID/URL bounds before side effects.
- Verification: PASS — `npm run check`: 79 passed, 2 skipped; Arduino compile `1,104,084 bytes (84%)`, RAM `53,368 bytes (16%)`; `git diff --check` and artifact cleanup PASS.
- Independent reviewer result: `NOT VERIFIED` — agent read current seam files but ended with `Operation interrupted: waiting for model response`; no approval verdict was fabricated.

### 2026-08-19 12:54 - Fix STOP_RECORDING state and add RESUME

- Đã sửa:
  - Backend accepts a terminal stale `STOPPED` status when `recording_id` matches the active recording, while preserving the newer stop request ID.
  - Firmware rebinds recorder completion to the latest request ID for `STOP_RECORDING`, `STOP`, and PLAY interrupt paths.
  - Added `AudioPlayer::resume()` and firmware `RESUME` command; RESUME continues the paused decoder, while PLAY remains a new playback from the beginning.
  - Added Backend `/api/v1/devices/{device_id}/resume`, Dashboard RESUME button, contract/docs, and regression tests.

- Verification:
  - PASS — targeted STOP/RESUME tests: 4 passed.
  - PASS — `npm run check`: 83 passed, 2 skipped.
  - PASS — Arduino compile: 1,104,276 bytes (84%), RAM 53,368 bytes (16%).
- NOT VERIFIED — physical recording/LED/speaker runtime and authenticated MQTT E2E.

### 2026-08-19 23:24 - Prepare source submission package

- Đã externalize firmware credentials:
  - tracked `main/config.h` chỉ còn safe defaults;
  - thêm `main/config.local.h.example`;
  - `main/config.local.h` bị ignore và không đưa vào package.
- Đã xóa khỏi working tree các runtime/generated artifact đã track: Python bytecode, WAV/E2E audio, metadata test, checkpoint `keyword_cnn.pt`, `.hermes` local state/plan và `test_artifacts`.
- Đã sửa training CLI để không import Torch/Numpy khi chỉ import hoặc chạy `--help`; thêm `--dataset`, `--epochs`, `--seed`.
- Đã tạo source package bên ngoài repo:
  - `C:\Users\vongb\Downloads\esp32-audio-system-source-final.zip`
  - 100 source/test/docs/config files plus manifest; package audit không có `.pyc`, audio, checkpoint hoặc credential override.
- Verification:
  - PASS — `npm run check`: 83 passed, 2 skipped.
  - PASS — `node frontend/test_app_contract.js`.
  - PASS — Arduino compile: 1,104,228 bytes (84%), RAM 53,368 bytes (16%).
  - PASS — `git diff --check`.
  - 2 skipped — authenticated MQTT tests cần credential broker do người dùng cấp.
  - NOT VERIFIED — hardware, authenticated MQTT-over-LAN, live Cloud/FCM và trained Torch inference.

### 2026-08-20 13:39 - Add Firebase Web Push registration

- Đã thêm Firebase Web Push cho Dashboard:
  - `frontend/public/firebase-notifications.js` xin quyền, đăng ký service worker, lấy FCM web token và gửi token về Backend.
  - `frontend/public/firebase-messaging-sw.js` hiển thị notification khi trang chạy nền.
  - `frontend/public/firebase-config.example.js` là template; `firebase-config.js` bị ignore.
- Đã thêm `POST /api/v1/notifications/register`; token được validate, không trả lại trong response, và cập nhật thread-safe vào FCM adapter.
- Verification:
  - PASS — `npm run check`: 85 passed, 2 skipped.
  - PASS — Firebase Web Push static contract and JS syntax tests.
  - PASS — Python compile notification route/service.
  - NOT VERIFIED — Firebase project/VAPID/browser permission và notification delivery trên điện thoại thật.

### 2026-08-20 13:39 - Add native Android FCM client

- Đã thêm thư mục `android/` cho native Android Kotlin:
  - `FirebaseMessagingService` xử lý notification foreground và token refresh;
  - Android 13+ notification permission;
  - tự POST FCM token tới `/api/v1/notifications/register`;
  - `google-services.json` và `gradle.properties` giữ local/ignored.
- Verification:
  - PASS — Android source contract: 2 passed.
  - PASS — full host check: 87 passed, 2 skipped.
  - NOT VERIFIED — Android Studio/Gradle/JDK 17 build, Firebase registration và phone delivery; host hiện chỉ có Java 8, chưa có Gradle/ADB/Android SDK.

### 2026-08-20 16:54 - Identify registered notification phones

- Đã mở rộng notification registry:
  - Android gửi `installation_id`, model/device name và platform cùng FCM token;
  - Backend lưu runtime registry, cập nhật `last_seen`, gửi notification tới mọi token đã đăng ký;
  - Dashboard gọi `GET /api/v1/notifications/devices` và hiển thị tên/platform/`ACTIVE` hoặc `STALE`;
  - API không trả FCM token; registry file bị ignore.
- Verification:
  - PASS — device registry/multi-device tests: 4 passed.
  - PASS — full host check trước cleanup: 91 passed, 2 skipped.
  - NOT VERIFIED — Android device heartbeat và FCM delivery thật.

### 2026-08-20 17:34 - Add Telegram notification provider

- Đã thêm provider `telegram` vào `NotificationService`:
  - gửi `sendMessage` tới Telegram Bot API;
  - format event/error/OFFLINE thành plain-text message tối đa 4096 ký tự;
  - fail-closed khi thiếu bot token hoặc chat ID;
  - FCM vẫn giữ làm provider tùy chọn.
- `.env.example` đặt `NOTIFICATION_PROVIDER=telegram` làm đường mặc định đơn giản cho MVP.
- Verification:
  - PASS — fake Telegram HTTP adapter: 2 tests.
  - NOT VERIFIED — Telegram Bot token/chat ID thật và message delivery thật.

### 2026-08-20 17:56 - Remove unused FCM/Web Push/Android source

- Đã xóa source không còn dùng sau khi chọn Telegram:
  - native Android module;
  - Firebase Web Push scripts/config/template;
  - FCM token registry route, persistence, config và tests.
- Giữ nguyên local `android/app/google-services.json` nếu người dùng đã có; file không được đọc, track hoặc đưa vào package.
- Telegram là provider notification duy nhất của runtime MVP.
- Verification:
  - PASS — full host check: 83 passed, 2 skipped.
  - PASS — active source reference scan không còn FCM/Web Push/Android implementation.
  - PASS — Telegram-only submission package: `C:\Users\vongb\Downloads\esp32-audio-system-source-final.zip` (83 source/test/docs/config files + manifest).
  - NOT VERIFIED — Telegram Bot token/chat ID thật và message delivery thật.

### 2026-08-21 02:07 - Fix recording duration, online notification, Cloud list, QoS and pause

- Recording:
  - Khôi phục `RECORDING_DEFAULT_SECONDS` về `5UL`; test contract ngăn regression về 1 giây.
  - File thực tế `rec_3db95b20.wav` có `18,944 samples = 1.184s`, phù hợp lỗi default 1 giây; firmware phải compile/upload lại.
  - Audio PCM chunks đổi từ QoS 0 sang QoS 1 để tránh mất gói làm WAV ngắn; Backend vẫn deduplicate sequence cũ.
- Telegram:
  - Thêm thông báo `ESP32 online` khi status chuyển sang ONLINE.
  - Retained OFFLINE ban đầu không bắn lặp; OFFLINE sau trạng thái ONLINE vẫn thông báo.
- Pause:
  - `AudioPlayer::pause()` dừng I2S DMA channel;
  - `resume()` khởi tạo lại output I2S; lỗi re-init chuyển thành playback failure có kiểm soát.
- Cloud/Web:
  - Thêm Firestore REST `list_metadata()` có decode kiểu Firestore và pagination giới hạn.
  - `GET /api/v1/audio` merge metadata Firestore với local records; Cloud lỗi thì fallback local.
  - Cập nhật `SETUP_NEW_DEVICE.md` với `CLOUD_PROVIDER`, `CLOUD_PROJECT_ID`, `CLOUD_ACCESS_TOKEN`, `PUBLIC_BASE_URL` LAN.
- Verification:
  - PASS — targeted new tests: 7 passed.
  - PASS — full host check: 91 passed, 2 skipped.
  - PASS — Python compile và `git diff --check`.
  - PASS — Arduino compile: 1,104,400 bytes (84%), RAM 53,368 bytes (16%); existing ESP8266Audio narrowing warning only.
  - NOT VERIFIED — physical ESP32 duration after reflash, QoS delivery over live broker, I2S pause/resume hardware, live Firestore read, Telegram live delivery.

### 2026-08-21 02:29 - Silence flush and generic error deduplication

- Pause now sets I2S gain to zero, flushes silence into the DMA buffer, stops the I2S channel, and restores gain before RESUME.
- Backend no longer sends a duplicate generic `DEVICE_ERROR` notification for a bare `status=ERROR`; it waits for the structured error topic such as `AUDIO_PLAYBACK_FAILED`.
- Verification:
  - PASS — full host check: 92 passed, 2 skipped.
  - PASS — firmware compile: 1,104,452 bytes (84%), RAM 53,368 bytes (16%).
  - PASS — pause silence and error dedup targeted tests.
  - NOT VERIFIED — physical speaker pause/resume and live playback transport.

### 2026-08-21 02:33 - Final upload gate inspection

- PASS — current source host checks: 92 passed, 2 skipped.
- PASS — current firmware compile: 1,104,452 bytes (84%), RAM 53,368 bytes (16%).
- BLOCKED / NOT VERIFIED — Arduino CLI detected only `COM3`–`COM6` as `Standard Serial over Bluetooth link`; no USB ESP32 serial device/CH340/CP210x was connected, so firmware upload and Serial hardware E2E were not attempted.
- Backend process was not listening on port 8000 during this gate; restart is required to load ONLINE/Cloud/error-dedup changes.
