#include "mqtt_manager.h"

#include <stdio.h>
#include <string.h>

#include "config.h"

namespace {
MqttManager* activeManager = nullptr;

void onMessage(int messageSize) {
  if (activeManager != nullptr) {
    activeManager->receiveCommand(messageSize);
  }
}
}  // namespace

MqttManager::MqttManager() : client_(networkClient_) {}

void MqttManager::begin(const char* host, uint16_t port, const char* deviceId,
                        const char* username, const char* password,
                        CommandCallback callback) {
  host_ = host;
  port_ = port;
  deviceId_ = deviceId;
  username_ = username;
  password_ = password;
  callback_ = callback;
  started_ = true;
  nextAttemptAt_ = 0;
  reconnectDelayMs_ = MQTT_CONNECT_RETRY_MS;
  snprintf(commandTopic_, sizeof(commandTopic_), "esp32/%s/command", deviceId_);
  snprintf(statusTopic_, sizeof(statusTopic_), "esp32/%s/status", deviceId_);
  snprintf(eventTopic_, sizeof(eventTopic_), "esp32/%s/event", deviceId_);
  snprintf(errorTopic_, sizeof(errorTopic_), "esp32/%s/error", deviceId_);
  snprintf(audioStartTopic_, sizeof(audioStartTopic_), "esp32/%s/audio/start", deviceId_);
  snprintf(audioEndTopic_, sizeof(audioEndTopic_), "esp32/%s/audio/end", deviceId_);
  // ArduinoMqttClient expects both values in milliseconds.
  client_.setKeepAliveInterval(MQTT_KEEPALIVE_SECONDS * 1000UL);
  client_.setConnectionTimeout(MQTT_SOCKET_TIMEOUT_SECONDS * 1000UL);
  client_.onMessage(onMessage);
  activeManager = this;
}

void MqttManager::update() {
  if (!started_) {
    return;
  }
  if (client_.connected()) {
    client_.poll();
    return;
  }
  connectIfDue();
}

bool MqttManager::isConnected() {
  return client_.connected();
}

void MqttManager::connectIfDue() {
  const uint32_t now = millis();
  if (static_cast<int32_t>(now - nextAttemptAt_) < 0) {
    return;
  }
  client_.setId(deviceId_);
  if (username_ != nullptr && username_[0] != '\0') {
    client_.setUsernamePassword(username_, password_ == nullptr ? "" : password_);
  }
  char willPayload[160];
  snprintf(willPayload, sizeof(willPayload),
           "{\"device_id\":\"%s\",\"status\":\"OFFLINE\",\"reason\":\"UNEXPECTED_DISCONNECT\"}",
           deviceId_);
  client_.beginWill(statusTopic_, strlen(willPayload), true, 1);
  client_.print(willPayload);
  client_.endWill();

  if (client_.connect(host_, port_) == 1) {
    client_.subscribe(commandTopic_, 1);
    char onlinePayload[96];
    snprintf(onlinePayload, sizeof(onlinePayload),
             "{\"device_id\":\"%s\",\"status\":\"ONLINE\"}", deviceId_);
    publishStatus(onlinePayload);
    reconnectDelayMs_ = MQTT_CONNECT_RETRY_MS;
    nextAttemptAt_ = now + reconnectDelayMs_;
    return;
  }

  nextAttemptAt_ = now + reconnectDelayMs_;
  if (reconnectDelayMs_ < MQTT_CONNECT_RETRY_MAX_MS) {
    reconnectDelayMs_ *= 2;
    if (reconnectDelayMs_ > MQTT_CONNECT_RETRY_MAX_MS) {
      reconnectDelayMs_ = MQTT_CONNECT_RETRY_MAX_MS;
    }
  }
}

bool MqttManager::publish(const char* topic, const char* payload,
                          bool retained) {
  if (payload == nullptr) {
    return false;
  }
  return publishBytes(topic, reinterpret_cast<const uint8_t*>(payload), strlen(payload), retained);
}

bool MqttManager::publishBytes(const char* topic, const uint8_t* payload,
                               size_t length, bool retained) {
  if (!client_.connected() || topic == nullptr || payload == nullptr) {
    return false;
  }
  if (client_.beginMessage(topic, length, retained, 1, false) == 0) {
    return false;
  }
  if (client_.write(payload, length) != length) {
    return false;
  }
  return client_.endMessage() == 1;
}

bool MqttManager::publishStatus(const char* payload) {
  return publish(statusTopic_, payload, true);
}

bool MqttManager::publishEvent(const char* payload) {
  return publish(eventTopic_, payload, false);
}

bool MqttManager::publishError(const char* payload) {
  return publish(errorTopic_, payload, false);
}

bool MqttManager::publishAudioStart(const char* recordingId, uint32_t sampleRate,
                                    uint8_t channels, uint8_t bitsPerSample) {
  if (recordingId == nullptr || recordingId[0] == '\0') {
    return false;
  }
  char payload[224];
  snprintf(payload, sizeof(payload),
           "{\"device_id\":\"%s\",\"recording_id\":\"%s\","
           "\"sample_rate\":%lu,\"channels\":%u,\"bits_per_sample\":%u,"
           "\"format\":\"pcm_s16le\"}",
           deviceId_, recordingId, static_cast<unsigned long>(sampleRate), channels,
           bitsPerSample);
  return publish(audioStartTopic_, payload, false);
}

bool MqttManager::publishAudioChunk(const char* recordingId, uint32_t sequence,
                                    const int16_t* samples, size_t sampleCount) {
  if (recordingId == nullptr || recordingId[0] == '\0' || samples == nullptr || sampleCount == 0) {
    return false;
  }
  char topic[160];
  snprintf(topic, sizeof(topic), "esp32/%s/audio/chunk/%s/%lu", deviceId_, recordingId,
           static_cast<unsigned long>(sequence));
  return publishBytes(topic, reinterpret_cast<const uint8_t*>(samples), sampleCount * sizeof(int16_t), false);
}

bool MqttManager::publishAudioEnd(const char* recordingId, uint32_t totalChunks,
                                  uint32_t sampleCount) {
  if (recordingId == nullptr || recordingId[0] == '\0') {
    return false;
  }
  char payload[192];
  snprintf(payload, sizeof(payload),
           "{\"device_id\":\"%s\",\"recording_id\":\"%s\","
           "\"total_chunks\":%lu,\"sample_count\":%lu}",
           deviceId_, recordingId, static_cast<unsigned long>(totalChunks),
           static_cast<unsigned long>(sampleCount));
  return publish(audioEndTopic_, payload, false);
}

void MqttManager::receiveCommand(int messageSize) {
  if (messageSize < 0 || messageSize >= COMMAND_BUFFER_SIZE) {
    while (client_.available()) {
      client_.read();
    }
    publishError("{\"device_id\":\"esp32_01\",\"error_code\":\"COMMAND_TOO_LARGE\",\"message\":\"Command payload exceeds buffer\"}");
    return;
  }
  static char payload[COMMAND_BUFFER_SIZE];
  size_t index = 0;
  while (client_.available() && index < sizeof(payload) - 1) {
    payload[index++] = static_cast<char>(client_.read());
  }
  payload[index] = '\0';
  if (callback_ != nullptr) {
    callback_(payload, index);
  }
}
