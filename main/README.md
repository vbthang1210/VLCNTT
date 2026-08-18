# ESP32 firmware

Arduino IDE/CLI sketch directory. Open `main.ino` directly.

## Libraries

Install via Arduino CLI or Arduino IDE:

- ArduinoMqttClient 0.1.8
- ArduinoJson 7.4.2
- ESP8266Audio 2.4.1
- Arduino-ESP32 Core 3.3.11+

`ESP_I2S.h` used by the microphone path is provided by Arduino-ESP32 Core; no extra microphone library is required.

## Configuration

Edit `config.h` locally:

- `WIFI_SSID` / `WIFI_PASSWORD`
- `MQTT_HOST` — must be the backend computer LAN IP for a physical ESP32; `127.0.0.1` is host-only.
- `DEVICE_ID`
- Speaker I2S pins for the actual external DAC.
- `LED_PIN` for the real LED/relay output.
- INMP441 pins if your wiring differs from the development defaults.

No credentials are committed by this project.

## INMP441 development wiring

Default microphone wiring in `config.h`:

| INMP441 | ESP32 |
| --- | --- |
| VDD | 3.3V |
| GND | GND |
| SCK / BCLK | GPIO 32 |
| WS / LRC | GPIO 33 |
| SD | GPIO 34 |
| L/R | GND |

`L/R -> GND` selects the left I2S slot, matching the firmware configuration.

The microphone uses I2S1 and the speaker path keeps its existing I2S output path. Voice capture runs only while speaker playback is inactive.

## Voice MQTT flow

The firmware captures 1-second, 16 kHz mono windows and publishes:

```text
vlcntt/{device_id}/audio/start   JSON, QoS 1
vlcntt/{device_id}/audio/data    PCM16 binary, QoS 0
vlcntt/{device_id}/audio/end     JSON, QoS 1
```

Start payload example:

```json
{
  "device_id": "esp32_01",
  "session_id": "mic_123_0",
  "sample_rate": 16000,
  "channels": 1,
  "sample_width": 2,
  "encoding": "pcm_s16le"
}
```

The backend saves a WAV only after a complete `audio/end`, then runs AI inference. Incomplete windows are not finalized; stale backend sessions expire and can be replaced by a later capture.

## Build

PowerShell / Arduino CLI example:

```powershell
arduino-cli compile --clean --warnings all `
  --libraries "C:\Users\<user>\Documents\Arduino\libraries" `
  --fqbn esp32:esp32:esp32 main
```

The firmware uses a bounded `AudioFileSourceBuffer` and HTTP stream. It does not allocate RAM based on total audio-file size.

Hardware upload, WiFi association, MQTT-over-LAN, INMP441 input, decoder, I2S speaker output, and physical LED/relay remain hardware-dependent verification steps.
