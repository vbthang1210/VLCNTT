#ifndef ESP32_AUDIO_CONFIG_H
#define ESP32_AUDIO_CONFIG_H

// Development defaults. Replace WiFi credentials and MQTT_HOST for hardware.
#define WIFI_SSID "BenThanh Apartment"
#define WIFI_PASSWORD "benthanh@"
#define MQTT_HOST "192.168.1.67"
#define MQTT_PORT 1883
#define MQTT_USERNAME "esp32_01"
#define MQTT_PASSWORD "123"
#define DEVICE_ID "esp32_01"

// Default external I2S DAC wiring; change for the actual board/DAC.
#define I2S_BCLK_PIN 26
#define I2S_WS_PIN 25
#define I2S_DOUT_PIN 22

// INMP441 input wiring. The microphone uses I2S1 so playback can keep I2S0.
#define MIC_I2S_BCLK_PIN 32
#define MIC_I2S_WS_PIN 33
#define MIC_I2S_SD_PIN 34
#define MIC_SAMPLE_RATE 16000UL
#define MIC_SAMPLES_PER_CHUNK 512
#define RECORDING_DEFAULT_SECONDS 5UL
#define RECORDING_MAX_SECONDS 60UL
#define MIC_MQTT_RECOVERY_TIMEOUT_MS 10000UL

#define MQTT_CONNECT_RETRY_MS 1000UL
#define MQTT_CONNECT_RETRY_MAX_MS 10000UL
#define MQTT_KEEPALIVE_SECONDS 30
#define MQTT_SOCKET_TIMEOUT_SECONDS 5
#define COMMAND_BUFFER_SIZE 512
#define AUDIO_HTTP_RETRY_COUNT 3
#define AUDIO_BUFFER_BYTES 4096

#endif
