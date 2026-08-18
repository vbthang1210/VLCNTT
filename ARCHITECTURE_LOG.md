# Architecture Log

## DEV-001 — Development defaults for first runnable stack

Status: DEVELOPMENT DEFAULT — production approval still required.

- Firmware sketch directory: `main/` so Arduino IDE/CLI can compile `main/main.ino` directly.
- Target board/FQBN: ESP32 Dev Module / `esp32:esp32:esp32`.
- Device ID: `esp32_01`.
- MQTT development broker: `127.0.0.1:1883` for host-side tests; an ESP32 cannot reach loopback, so hardware tests require replacing `MQTT_HOST` with the host LAN address and allowing the broker listener/firewall.
- MQTT auth: anonymous for local development only.
- Canonical MQTT contract follows `PROJECT_RULES.md`: per-device topics, uppercase commands/statuses, `request_id`, QoS 1, command retain=false, status retain=true, LWT.
- Backend local metadata index substitutes for Cloud Database until a Cloud provider/credential contract is supplied. Real audio remains in Backend storage.
- Backend framework: Flask; MQTT client: Paho MQTT.
- Frontend: Node.js built-in HTTP server plus browser JavaScript; browser talks only to Backend API.
- Supported upload formats: MP3 and WAV, maximum 20 MiB.
- Development volume range: integer 0..100. This range is an implementation decision because the source contract gives an example but does not state bounds.
- ESP32 audio library: ESP8266Audio 2.4.1. HTTP audio is streamed; no whole-file audio allocation is used.
- ESP32 I2S development pins: BCLK=26, WS/LRC=25, DOUT=22. These are hardware assumptions and must be changed for a different DAC/board.
- TTS endpoint returns an explicit not-configured error until a real provider is selected; no synthetic audio is presented as TTS.

## CONFLICT-001 — FLOW.md versus PROJECT_RULES.md

`FLOW.md` contains older lowercase/generic MQTT examples. `PROJECT_RULES.md` is authoritative for implementation: `esp32/{device_id}/{type}`, uppercase command/status values, required `request_id`, and the specified QoS/retain behavior. This decision does not rewrite either source document.

## DEV-002 — External provider boundaries

Status: IMPLEMENTED — real provider smoke tests require user-supplied, non-committed configuration.

- TTS provider: `TTS_PROVIDER=openai_compatible`; the endpoint must implement an OpenAI-compatible `/audio/speech` POST response containing MP3 or WAV bytes.
- Firestore metadata: `CLOUD_PROVIDER=firestore`; only light audio metadata and device status are sent through the Firestore REST API. Audio bytes remain in Backend storage.
- Push notifications: `NOTIFICATION_PROVIDER=fcm`; MQTT events, device errors and OFFLINE status are sent through FCM HTTP v1 to the configured device token.
- Provider calls use bounded timeouts: TTS 15 seconds, Firestore/FCM 10 seconds.
- Missing provider configuration fails closed; fake-HTTP tests verify request contracts without pretending that an external delivery occurred.

## DEV-003 — INMP441 PCM recording pipeline

Status: HOST IMPLEMENTED / firmware compile and hardware runtime NOT VERIFIED.

- ESP32 command contract: `START_RECORDING` and `STOP_RECORDING` on `esp32/{device_id}/command`.
- Audio topics: JSON start/end markers on `esp32/{device_id}/audio/start` and `/audio/end`; raw PCM s16le chunks on `/audio/chunk/{recording_id}/{sequence}`.
- Audio contract: 16 kHz, mono, 16-bit PCM; firmware chunk size is 512 samples (1024 bytes) before MQTT overhead.
- Backend assembles ordered chunks in a temporary file, writes a WAV header, and persists `rec_xxx.wav` plus local metadata.
- Browser uses the Backend stream endpoint for `<audio controls>` and the download endpoint; it never connects to MQTT directly.
- Recording duration defaults to 5 seconds and is capped at 60 seconds in development settings.
