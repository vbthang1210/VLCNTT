#ifndef ESP32_AUDIO_CONFIG_H
#define ESP32_AUDIO_CONFIG_H

// Development defaults. Replace WiFi credentials and MQTT_HOST for hardware.
#define WIFI_SSID "YOUR_WIFI_SSID"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"
#define MQTT_HOST "127.0.0.1"
#define MQTT_PORT 1883
#define MQTT_USERNAME ""
#define MQTT_PASSWORD ""
#define DEVICE_ID "esp32_01"

// Light output. GPIO 2 is a development default and is commonly connected
// to an onboard LED on ESP32 dev boards. Change this for the real lamp/relay.
#define LED_PIN 2

// Speaker I2S output wiring.
#define I2S_BCLK_PIN 26
#define I2S_WS_PIN 25
#define I2S_DOUT_PIN 22

// INMP441 microphone I2S input wiring.
// Development default: L/R pin of the INMP441 is tied to GND (left slot).
#define MIC_I2S_BCLK_PIN 32
#define MIC_I2S_WS_PIN 33
#define MIC_I2S_DIN_PIN 34
#define MIC_SAMPLE_RATE 16000
#define MIC_CAPTURE_MS 1000UL
#define MIC_WINDOW_GAP_MS 100UL
#define MIC_READ_SAMPLES 256

#define MQTT_CONNECT_RETRY_MS 1000UL
#define MQTT_CONNECT_RETRY_MAX_MS 10000UL
#define MQTT_KEEPALIVE_SECONDS 30
#define MQTT_SOCKET_TIMEOUT_SECONDS 5
#define COMMAND_BUFFER_SIZE 512
#define AUDIO_HTTP_RETRY_COUNT 3
#define AUDIO_BUFFER_BYTES 4096

#endif
