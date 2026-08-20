# ESP32 firmware

Arduino IDE/CLI sketch directory. Open `main.ino` directly.

## Libraries

Install via Arduino CLI or Arduino IDE:

- ArduinoMqttClient 0.1.8
- ArduinoJson 7.4.2
- ESP8266Audio 2.4.1
- Arduino-ESP32 Core 3.3.11+

## Configuration

Copy `config.local.h.example` to `config.local.h` and edit the ignored local override:

- `WIFI_SSID` / `WIFI_PASSWORD`
- `MQTT_HOST` — must be the backend computer LAN IP for a physical ESP32; `127.0.0.1` is host-only.
- `DEVICE_ID`
- I2S pins for the actual external DAC.
- `MIC_I2S_BCLK_PIN`, `MIC_I2S_WS_PIN`, and `MIC_I2S_SD_PIN` for the INMP441.

The tracked `config.h` contains submission-safe defaults. Never put real credentials in `config.h` or commit `config.local.h`.

## Build

```bash
arduino-cli compile --clean --warnings all \
  --libraries "C:\\Users\\<user>\\Documents\\Arduino\\libraries" \
  --fqbn esp32:esp32:esp32 main
```

The firmware uses a bounded `AudioFileSourceBuffer` and HTTP stream. It does not allocate RAM based on total audio-file size.

The INMP441 recorder captures 16 kHz mono 16-bit PCM on I2S1. It publishes a JSON
start marker, bounded raw PCM MQTT chunks, and a JSON end marker. The Backend
assembles those chunks into a WAV file; MQTT never carries the completed WAV file.

Hardware upload, WiFi association, MQTT-over-LAN, decoder, I2S, and speaker output remain hardware-dependent verification steps.
