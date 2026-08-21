#ifndef ESP32_AUDIO_CONFIG_H
#define ESP32_AUDIO_CONFIG_H

// Submission-safe defaults. Put real WiFi/MQTT values in config.local.h.
#if defined(__has_include)
#if __has_include("config.local.h")
#include "config.local.h"
#endif
#endif

#ifndef WIFI_SSID
#define WIFI_SSID "BenThanh Apartment"
#endif
#ifndef WIFI_PASSWORD
#define WIFI_PASSWORD "benthanh@"
#endif
#ifndef MQTT_HOST
#define MQTT_HOST "192.168.1.67"
#endif
#ifndef MQTT_PORT
#define MQTT_PORT 1883
#endif
#ifndef MQTT_USERNAME
#define MQTT_USERNAME "esp32_01"
#endif
#ifndef MQTT_PASSWORD
#define MQTT_PASSWORD "123"
#endif
#ifndef DEVICE_ID
#define DEVICE_ID "esp32_01"
#endif
#ifndef LED_PIN
#define LED_PIN 2
#endif

#ifndef I2S_BCLK_PIN
#define I2S_BCLK_PIN 26
#endif
#ifndef I2S_WS_PIN
#define I2S_WS_PIN 25
#endif
#ifndef I2S_DOUT_PIN
#define I2S_DOUT_PIN 27
#endif

#ifndef MIC_I2S_BCLK_PIN
#define MIC_I2S_BCLK_PIN 32
#endif
#ifndef MIC_I2S_WS_PIN
#define MIC_I2S_WS_PIN 33
#endif
#ifndef MIC_I2S_SD_PIN
#define MIC_I2S_SD_PIN 34
#endif
#ifndef MIC_SAMPLE_RATE
#define MIC_SAMPLE_RATE 16000UL
#endif
#ifndef MIC_SAMPLES_PER_CHUNK
#define MIC_SAMPLES_PER_CHUNK 512
#endif
#ifndef RECORDING_DEFAULT_SECONDS
#define RECORDING_DEFAULT_SECONDS 5UL
#endif
#ifndef RECORDING_MAX_SECONDS
#define RECORDING_MAX_SECONDS 60UL
#endif
#ifndef MIC_MQTT_RECOVERY_TIMEOUT_MS
#define MIC_MQTT_RECOVERY_TIMEOUT_MS 10000UL
#endif

#ifndef MQTT_CONNECT_RETRY_MS
#define MQTT_CONNECT_RETRY_MS 1000UL
#endif
#ifndef MQTT_CONNECT_RETRY_MAX_MS
#define MQTT_CONNECT_RETRY_MAX_MS 10000UL
#endif
#ifndef MQTT_KEEPALIVE_SECONDS
#define MQTT_KEEPALIVE_SECONDS 30
#endif
#ifndef MQTT_SOCKET_TIMEOUT_SECONDS
#define MQTT_SOCKET_TIMEOUT_SECONDS 5
#endif
#ifndef COMMAND_BUFFER_SIZE
#define COMMAND_BUFFER_SIZE 512
#endif
#ifndef AUDIO_HTTP_RETRY_COUNT
#define AUDIO_HTTP_RETRY_COUNT 3
#endif
#ifndef AUDIO_BUFFER_BYTES
#define AUDIO_BUFFER_BYTES 4096
#endif

#endif
