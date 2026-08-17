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

// Default external I2S DAC wiring; change for the actual board/DAC.
#define I2S_BCLK_PIN 26
#define I2S_WS_PIN 25
#define I2S_DOUT_PIN 22

#define MQTT_CONNECT_RETRY_MS 1000UL
#define MQTT_CONNECT_RETRY_MAX_MS 10000UL
#define MQTT_KEEPALIVE_SECONDS 30
#define MQTT_SOCKET_TIMEOUT_SECONDS 5
#define COMMAND_BUFFER_SIZE 512
#define AUDIO_HTTP_RETRY_COUNT 3
#define AUDIO_BUFFER_BYTES 4096

#endif
