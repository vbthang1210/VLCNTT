# PROJECT TASKS — EXECUTABLE IMPLEMENTATION TRACKER

Last refreshed: 2026-08-15

## Source-of-truth and scope

- Architecture/contract: `PROJECT_RULES.md`.
- Agent workflow: `AGENT_WORKFLOW.md`.
- Flow examples: `FLOW.md`; older generic/lowercase MQTT examples do not override `PROJECT_RULES.md`.
- Development defaults: `ARCHITECTURE_LOG.md`.
- Current task: `TASK.md`.
- Historical execution notes: `LOG.md`.
- This tracker records actual implementation and verification, not plans presented as completed.

## Status vocabulary

- `IMPLEMENTED`: source exists; required verification may be incomplete.
- `PASS`: the named check actually ran and passed.
- `PARTIAL`: only part of acceptance criteria ran.
- `NOT VERIFIED`: required hardware/provider/cloud evidence is unavailable.
- `BLOCKED`: implementation cannot be completed without a missing decision/dependency.

## Architecture dependencies

```text
ESP32 WiFi
  -> MQTT contract / Mosquitto
  -> Backend API + audio storage + MQTT bridge
  -> Node frontend
  -> hardware/cloud/TTS/notification integration
```

## EPIC ESP — ESP32 firmware

### ESP-01.1 — Preserve Arduino sketch entry point
Status: `IMPLEMENTED` / compile `PASS`.

- Files: `main/main.ino`, same-level `.h`/`.cpp` modules.
- Decision: folder is `main/` so `main.ino` compiles directly under Arduino IDE/CLI.
- Evidence: Arduino CLI compile has passed with ESP32 Core 3.3.11.

### ESP-02.1 — WiFi station initialization
Status: `IMPLEMENTED` / compile `PASS` / hardware `NOT VERIFIED`.

- Uses `WIFI_STA`.
- Credentials are placeholders in `config.h`; no real secret is committed.

### ESP-02.2 — Non-blocking WiFi connection attempts
Status: `IMPLEMENTED` / static `PASS` / compile `PASS` / hardware `NOT VERIFIED`.

- `WifiManager` uses `millis()` gating and no manager retry loop/delay.

### ESP-02.3 — WiFi state reporting
Status: `IMPLEMENTED` / static `PASS` / compile `PASS` / hardware `NOT VERIFIED`.

- Reports connected/disconnected transitions over Serial.

### ESP-02.4 — Bounded WiFi reconnect backoff
Status: `IMPLEMENTED` / static `PASS` / compile `PASS` / hardware `NOT VERIFIED`.

- Backoff: `1s, 2s, 4s, 8s, 10s`, capped at 10s.

### ESP-03.1 — Development runtime configuration
Status: `IMPLEMENTED` as explicit development defaults; production/hardware `NOT VERIFIED`.

- `main/config.h`: device `esp32_01`, anonymous local MQTT, default I2S pins.
- Hardware must replace WiFi credentials and loopback broker host.

### ESP-03.2 — Arduino MQTT manager
Status: `IMPLEMENTED` / compile `PASS` / hardware `NOT VERIFIED`.

- Uses ArduinoMqttClient.
- Per-device command/status/event/error topics.
- Command subscription QoS 1.
- Status/event/error publish methods use QoS 1; status retained.
- LWT status OFFLINE retained; ONLINE status on successful connection.
- Reconnect backoff is bounded.

### ESP-03.3 — MQTT command validation and dispatch
Status: `IMPLEMENTED` / compile `PASS` / device runtime `NOT VERIFIED`.

- Validates JSON, `request_id`, command, PLAY fields and volume range.
- Supports `PLAY`, `PAUSE`, `RESUME`, `STOP`, `SET_VOLUME`.
- Unknown/invalid commands publish error payloads.

### ESP-04.1 — HTTP streaming audio source
Status: `IMPLEMENTED` / compile `PASS` / hardware decoder/network `NOT VERIFIED`.

- Uses ESP8266Audio `AudioFileSourceHTTPStream` plus fixed `AUDIO_BUFFER_BYTES=4096` buffer.
- HTTP retries limited to 3.
- Does not allocate total file size.

### ESP-04.2 — MP3/WAV decoder and I2S output
Status: `IMPLEMENTED` / compile `PASS` / DAC/speaker `NOT VERIFIED`.

- MP3/WAV generator selected by format query/URL.
- External I2S defaults BCLK 26 / WS 25 / DOUT 22.
- Actual DAC wiring and playback require hardware.

### ESP-04.3 — Playback session lifecycle
Status: `IMPLEMENTED` / compile `PASS` / hardware `NOT VERIFIED`.

- One active playback session.
- New PLAY stops/releases previous session.
- STOP releases generator, buffer, HTTP source and I2S.
- PAUSE reports PAUSED.
- RESUME continues the paused decoder; PLAY remains a new playback from the beginning.
- Completion emits STOPPED status and `PLAY_COMPLETED` event.
- Stream failure emits ERROR status and `AUDIO_DOWNLOAD_FAILED`.

## EPIC MQTT — communication

### MQTT-01 — Canonical topics and QoS
Status: `IMPLEMENTED` / local broker `PASS` / ESP32-over-LAN `NOT VERIFIED`.

- Backend publishes `esp32/{device_id}/command`, QoS 1, retain false.
- Backend subscribes status/event/error wildcard topics, QoS 1.
- Local Mosquitto CONNECT/PUBLISH/PUBACK and Paho round-trip test pass.

### MQTT-02 — Status, error, event and stale response handling
Status: `IMPLEMENTED` / unit test `PASS`.

- Error topic becomes `ERROR` state with structured error.
- Event topic is retained separately as `last_event`.
- Older request responses do not replace current request state.

## EPIC BE — Python Backend

### BE-01 — Flask application and configuration
Status: `IMPLEMENTED` / import `PASS` / runtime health `PASS`.

Files:

- `backend/app/__init__.py`
- `backend/app/config.py`
- `backend/run.py`
- `backend/.env.example`

### BE-02 — Audio upload validation and backend storage
Status: `IMPLEMENTED` / tests `PASS` / manual WAV upload `PASS`.

- MP3/WAV extension and MIME validation.
- 20 MiB limit.
- Generated physical names.
- Backend-owned storage only.
- WAV metadata and MP3 ffprobe metadata.

### BE-03 — Audio metadata/list/get/stream APIs
Status: `IMPLEMENTED` / tests `PASS` / HTTP stream `PASS`.

Routes:

- `GET /api/v1/audio`
- `GET /api/v1/audio/{audio_id}`
- `POST /api/v1/audio/upload`
- `GET /api/v1/audio/{audio_id}/stream`

### BE-04 — Device command APIs
Status: `IMPLEMENTED` / route tests `PASS` / local MQTT command path `PARTIAL`.

Routes:

- `GET /api/v1/devices/{device_id}/status`
- `POST /api/v1/devices/{device_id}/play`
- `POST /api/v1/devices/{device_id}/pause`
- `POST /api/v1/devices/{device_id}/resume`
- `POST /api/v1/devices/{device_id}/stop`
- `POST /api/v1/devices/{device_id}/volume`

Backend returns command acceptance only; it does not claim PLAYING before device status.

### BE-05 — TTS provider boundary
Status: `IMPLEMENTED` / fake-HTTP adapter tests `PASS` / real provider `NOT VERIFIED`.

- `TTS_PROVIDER=openai_compatible` enables an environment-configured OpenAI-compatible `/audio/speech` adapter.
- Generated MP3/WAV bytes are saved through the existing Backend `AudioRepository`; audio is not sent to Cloud.
- `POST /api/v1/audio/tts` persists returned metadata through the Cloud boundary.
- Missing endpoint/key/model/voice remains fail-closed as `TTS_NOT_CONFIGURED` (501).
- No synthetic audio is presented as real provider output.

### BE-06 — Cloud metadata persistence
Status: `IMPLEMENTED` / fake-HTTP adapter tests `PASS` / real Firestore `NOT VERIFIED`.

- `CLOUD_PROVIDER=firestore` enables Firestore REST metadata writes.
- Upload/TTS metadata is written to `audio_metadata/{audio_id}`.
- Device status is written to `device_status/{device_id}` from MQTT state ingestion.
- Only light metadata/status fields are sent; Backend remains source of truth for audio bytes.
- Missing project/token remains fail-closed; local development keeps `cloud_synced=false`.

### BE-07 — Push notification adapter
Status: `IMPLEMENTED` / fake-HTTP adapter and MQTT dispatch tests `PASS` / real FCM `NOT VERIFIED`.

- `NOTIFICATION_PROVIDER=fcm` enables FCM HTTP v1.
- MQTT events, device errors and `OFFLINE` status are forwarded to the configured device token.
- Notification failure does not block MQTT state ingestion.
- Missing FCM configuration remains fail-closed; no credentials are committed.

## EPIC FE — Node.js frontend

### FE-01 — Node static server
Status: `IMPLEMENTED` / syntax `PASS` / HTTP smoke `PASS`.

- `frontend/server.js` uses Node built-in HTTP.
- Path traversal is rejected.

### FE-02 — API-only audio/device UI
Status: `IMPLEMENTED` / syntax `PASS`.

- Upload, TTS request, list, metadata selection, PLAY, PAUSE, STOP, volume and status polling.
- Browser calls Backend REST only; no MQTT/ESP32/Cloud access.
- Browser runtime requires Backend CORS and a browser environment; no browser automation evidence recorded.

## EPIC TEST / INTEGRATION

### TEST-01 — Backend automated tests
Status: `PASS`.

Actual result:

```text
23 passed in 4.56s
```

Coverage includes health, upload, WAV metadata, list, stream bytes, 404, volume validation, provider boundaries, fake-HTTP TTS/Firestore/FCM adapters, upload/TTS metadata persistence, MQTT status persistence, notification dispatch, stale MQTT responses, error mapping, event storage and local Mosquitto/Paho QoS 1 round-trip.

### TEST-02 — Frontend syntax and HTTP smoke
Status: `PASS` for available host checks.

- `node --check server.js`: pass.
- `node --check public/app.js`: pass.
- `GET http://127.0.0.1:3000/`: HTTP 200.
- `GET http://127.0.0.1:3000/app.js`: HTTP 200.

### TEST-03 — Arduino compile
Status: `PASS` / hardware `NOT VERIFIED`.

Command:

```text
arduino-cli compile --clean --warnings all --libraries C:\Users\vongb\Documents\Arduino\libraries --fqbn esp32:esp32:esp32 C:\Users\vongb\Downloads\t\main
```

Latest result:

```text
exit code: 0
Sketch: 1090740 bytes (83%) of 1310720
Global: 49936 bytes (15%), 277744 bytes free
```

One warning originates in ESP8266Audio's `AudioOutputPDM.cpp` narrowing conversion; it does not fail the build and is outside project source.

### TEST-04 — End-to-end host integration
Status: `PARTIAL`.

PASS evidence:

- Mosquitto local broker on `127.0.0.1:1883`.
- Backend health returned HTTP 200 while server was running.
- Manual WAV upload returned HTTP 201.
- Audio stream returned HTTP 200 with `audio/wav` and correct bytes.
- Backend PLAY returned HTTP 202 with canonical command acceptance.
- Broker status publish/retained subscription worked.
- Backend state updated from broker status to ONLINE.
- Frontend served HTML/JS over HTTP 200.
- Live Backend `POST /api/v1/devices/esp32_01/stop` returned HTTP 202.
- A Mosquitto subscriber captured `esp32/esp32_01/command` with `request_id=req_capture_stop_01` and `command=STOP`.
- `hermes verify --json` passed bootstrap, root test command, and readiness `http://127.0.0.1:8000/` with HTTP 200.

Not verified:

- ESP32 physical WiFi/MQTT-over-LAN.
- Real MP3/WAV decode and I2S speaker output.
|- Real TTS provider generation (provider credentials/endpoint not configured).
|- Real Cloud database persistence (Firestore credentials/token not configured).
|- Real push notification delivery (FCM credentials/device token not configured).
- Browser interaction automation.

## Current blockers

1. No ESP32 board/recognized serial device is attached; hardware verification is `NOT VERIFIED`.
2. Mosquitto is loopback-only; physical ESP32 needs LAN bind/firewall and `MQTT_HOST` change.
3. I2S pins/DAC model are development defaults and need hardware confirmation.
4. TTS, Cloud Database and Push Notification credentials/providers are absent; adapters remain explicit and fail closed.
5. `FLOW.md` retains older generic/lowercase examples; `PROJECT_RULES.md` remains authoritative.

## Next execution order

1. Attach/configure ESP32 + DAC and run WiFi/MQTT/stream/I2S hardware tests.
2. Configure a real TTS provider and run provider smoke tests.
3. Configure Cloud metadata/notification providers and run Firestore/FCM smoke tests.
4. Run browser E2E against the real device.

## EPIC REC — INMP441 microphone recording

### REC-01 — MQTT PCM chunk ingestion and WAV persistence
Status: `IMPLEMENTED` / Backend tests `PASS` / Mosquitto-to-ESP32 `NOT VERIFIED`.

- Backend subscribes to `esp32/+/audio/#`.
- Ordered raw PCM chunks are assembled into a temporary file.
- Final WAV is 16 kHz, mono, 16-bit and stored as `rec_xxx.wav`.
- Local metadata is written to `backend/storage/metadata.json`.

### REC-02 — Record control and Web playback/download
Status: `IMPLEMENTED` / Backend API + Node syntax `PASS` / browser/device E2E `NOT VERIFIED`.

- `POST /api/v1/devices/{device_id}/record/start` publishes `START_RECORDING`.
- `POST /api/v1/devices/{device_id}/record/stop` publishes `STOP_RECORDING`.
- Dashboard renders `<audio controls>` and a download link for every record.
- Dashboard derives Backend URL from the serving hostname, shows recording countdown, and exposes a DELETE action.
- `DELETE /api/v1/audio/{audio_id}` removes the local file and metadata atomically.
- Cloud metadata sync failure does not discard a successfully stored local upload.

### REC-03 — ESP32 INMP441 capture
Status: `IMPLEMENTED` in source / Arduino compile and hardware runtime `NOT VERIFIED`.

- I2S1 capture with configurable INMP441 pins.
- 512-sample PCM chunks, start/end markers, and bounded recording duration.
- Requires Arduino-ESP32, ArduinoMqttClient and an actual INMP441/ESP32 wiring test.

### REC-04 — Reliability and arbitration safeguards
Status: `IMPLEMENTED` / host regression tests `PASS` / hardware runtime `NOT VERIFIED`.

- Playback and recording are mutually exclusive; `STOP` stops both.
- Volume changes publish an event without forcing the device to `IDLE`.
- Oversized command errors use the configured runtime device ID.
- Incomplete recording sessions expire after `RECORDING_SESSION_TIMEOUT_SECONDS` (default 15 seconds).
- `STOP_RECORDING` rebinds the recorder completion response to the stop request; Backend also accepts a stale terminal `STOPPED` for the same recording ID.

## EPIC LED-AI — LED control and optional keyword inference

### LED-01 — ESP32 LIGHT command
Status: `IMPLEMENTED` / firmware compile and contract test `PASS` / physical LED runtime `NOT VERIFIED`.

- `LIGHT` accepts only `ON`/`OFF`.
- ESP32 drives configurable `LED_PIN` (development default GPIO2).
- ESP32 emits `LIGHT_CHANGED` without changing the audio status contract.

### AI-01 — Optional keyword runtime
Status: `IMPLEMENTED` source/tests / model inference `NOT VERIFIED` until a checkpoint exists.

- Missing Torch/model does not crash Backend; health reports `ai_ready=false`.
- `bat` maps to `LIGHT ON`; `tat` maps to `LIGHT OFF` at confidence >= 0.80.
- Only approximately-one-second recordings are eligible for keyword inference.

### AI-02 — Optional training
Status: `IMPLEMENTED` scripts / training quality `NOT VERIFIED` until a real dataset is supplied.

- Optional dependencies are isolated in `backend/requirements-ai.txt`.
- Preprocess expects `dataset/raw/{bat,tat,unknown,silence}`.
- Training writes `backend/storage/models/keyword_cnn.pt`.
