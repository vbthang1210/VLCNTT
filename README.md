# ESP32 Audio System

Development MVP for the architecture described in `PROJECT_RULES.md`.

## Current layout

```text
main/                         Arduino sketch
backend/                      Flask API, storage, MQTT bridge, tests
frontend/                     Node.js static web UI/server
docs/PROJECT_TASKS.md         implementation status
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

The ESP32 cannot connect to a loopback broker. For hardware, set `MQTT_HOST` in `main/config.h` to the development computer's LAN IP and configure Mosquitto/firewall accordingly.

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

## Firmware

Open `main/main.ino` in Arduino IDE or compile directly:

```bash
arduino-cli compile --fqbn esp32:esp32:esp32 main
```

Install/select Arduino-ESP32 Core and the libraries listed in `main/README.md` or the Arduino sketchbook. Fill WiFi values and adjust MQTT/I2S settings before hardware use.

## Verification status

Host compile/API tests can be run locally. ESP32 upload, WiFi, MQTT-over-LAN, decoder, I2S and speaker behavior require the target hardware and are not claimed as verified without evidence.
