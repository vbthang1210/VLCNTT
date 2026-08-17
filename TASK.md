# Current Task

## Goal
Implement a runnable development MVP across Backend, Frontend, MQTT boundary, and Arduino firmware without claiming hardware verification that has not run.

## Acceptance Criteria

- Backend exposes the specified audio/device API paths.
- Audio files are stored in Backend storage, not MQTT.
- Backend can publish canonical MQTT commands when enabled.
- Frontend talks only to Backend API.
- ESP32 sketch compiles with Arduino-ESP32 and uses streaming audio APIs.
- Tests and compile output are recorded honestly.

## Status
PARTIAL — host MVP and provider adapters implemented; real provider calls and hardware remain unverified.

## Current Issue
No real TTS, Firestore, or FCM credentials/provider endpoint are configured. Development adapters use environment variables and fail closed when absent. Target ESP32 board and I2S hardware are also unavailable. The host-side Backend/Frontend/MQTT checks pass; this is not an end-to-end hardware/provider completion claim.

## Related Files

- `PROJECT_RULES.md`
- `AGENT_WORKFLOW.md`
- `FLOW.md`
- `ARCHITECTURE_LOG.md`
- `backend/`
- `frontend/`
- `main/`

## Next Step
Provide non-committed provider configuration (`TTS_*`, `CLOUD_*`, `NOTIFICATION_*`) to run real provider smoke tests. Separately attach ESP32/DAC, set local WiFi credentials, replace loopback MQTT host with the computer LAN IP, then run WiFi/MQTT/stream/I2S tests.
