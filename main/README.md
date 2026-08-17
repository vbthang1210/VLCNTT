# ESP32 firmware

Arduino IDE/CLI sketch directory. Open `main.ino` directly.

## Libraries

Install via Arduino CLI or Arduino IDE:

- ArduinoMqttClient 0.1.8
- ArduinoJson 7.4.2
- ESP8266Audio 2.4.1
- Arduino-ESP32 Core 3.3.11+

## Configuration

Edit `config.h` locally:

- `WIFI_SSID` / `WIFI_PASSWORD`
- `MQTT_HOST` — must be the backend computer LAN IP for a physical ESP32; `127.0.0.1` is host-only.
- `DEVICE_ID`
- I2S pins for the actual external DAC.

No credentials are committed by this project.

## Build

```bash
arduino-cli compile --clean --warnings all \
  --libraries "C:\\Users\\<user>\\Documents\\Arduino\\libraries" \
  --fqbn esp32:esp32:esp32 main
```

The firmware uses a bounded `AudioFileSourceBuffer` and HTTP stream. It does not allocate RAM based on total audio-file size.

Hardware upload, WiFi association, MQTT-over-LAN, decoder, I2S, and speaker output remain hardware-dependent verification steps.
