# Current Task

## Goal
Add the INMP441 microphone recording flow across Backend, Frontend, MQTT, and Arduino firmware without claiming hardware verification that has not run.

## Acceptance Criteria

- Backend exposes the specified audio/device API paths.
- Audio files are stored in Backend storage, not MQTT.
- Backend can publish canonical MQTT commands when enabled.
- Frontend talks only to Backend API.
- ESP32 sketch compiles with Arduino-ESP32 and uses streaming audio APIs.
- ESP32 can publish bounded 16 kHz mono 16-bit PCM recording chunks over the recording MQTT topics.
- Backend assembles the chunks into `rec_xxx.wav` and persists local metadata.
- Web Dashboard can play and download the resulting recording.
- Tests and compile output are recorded honestly.

## Status
PARTIAL — host recording flow, firmware safeguards, cleanup timeout, audio deletion, responsive Dashboard, LED command, and optional AI/training sources are implemented; Arduino compile and host tests are PASS, while real MQTT-over-LAN, microphone/LED capture, trained-model inference, and browser/device E2E remain unverified.

## Current Issue
No target ESP32/INMP441 board or LAN MQTT setup is available. The host-side Backend/Frontend/MQTT contract checks pass; this is not an end-to-end hardware completion claim. TTS, Firestore, and FCM remain separately unconfigured.

## Related Files

- `PROJECT_RULES.md`
- `AGENT_WORKFLOW.md`
- `FLOW.md`
- `ARCHITECTURE_LOG.md`
- `backend/`
- `frontend/`
- `main/`
- `backend/tests/test_recording.py`
- `PROJECT_RULES.md`

## Next Step
Install/use Arduino CLI, attach ESP32 + INMP441, set local WiFi credentials, replace loopback MQTT host with the computer LAN IP, then run MQTT chunk capture and WAV playback tests. Provider smoke tests remain a separate optional step.
