#include "mqtt_manager.h"

#include <stdio.h>
#include <string.h>

#include <ArduinoJson.h>

#include "config.h"

namespace {
MqttManager* activeManager = nullptr;

bool serializeMqttJson(JsonDocument& document, char* payload, size_t capacity) {
  const size_t required = measureJson(document);
  const size_t written = serializeJson(document, payload, capacity);
  return required + 1 <= capacity && written < capacity && written == required;
}

bool isSafeIdentifier(const char* value) {
  if (value == nullptr || value[0] == '\0') {
    return false;
  }
  for (size_t index = 0; value[index] != '\0'; ++index) {
    if (index >= 63) {
      return false;
    }
    const char character = value[index];
    if (!((character >= 'a' && character <= 'z') ||
          (character >= 'A' && character <= 'Z') ||
          (character >= '0' && character <= '9') ||
          character == '_' || character == '-')) {
      return false;
    }
  }
  return true;
}

bool buildTopic(char* target, size_t capacity, const char* deviceId,
                const char* suffix) {
  const int written = snprintf(target, capacity, "esp32/%s/%s", deviceId, suffix);
  return written >= 0 && static_cast<size_t>(written) < capacity;
}

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
  if (!isSafeIdentifier(deviceId_) ||
      !buildTopic(commandTopic_, sizeof(commandTopic_), deviceId_, "command") ||
      !buildTopic(statusTopic_, sizeof(statusTopic_), deviceId_, "status") ||
      !buildTopic(eventTopic_, sizeof(eventTopic_), deviceId_, "event") ||
      !buildTopic(errorTopic_, sizeof(errorTopic_), deviceId_, "error") ||
      !buildTopic(audioStartTopic_, sizeof(audioStartTopic_), deviceId_, "audio/start") ||
      !buildTopic(audioEndTopic_, sizeof(audioEndTopic_), deviceId_, "audio/end")) {
    started_ = false;
    return;
  }
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
  JsonDocument will;
  will["device_id"] = deviceId_ == nullptr ? "" : deviceId_;
  will["status"] = "OFFLINE";
  will["reason"] = "UNEXPECTED_DISCONNECT";
  char willPayload[160];
  if (!serializeMqttJson(will, willPayload, sizeof(willPayload))) {
    nextAttemptAt_ = now + reconnectDelayMs_;
    return;
  }
  client_.beginWill(statusTopic_, strlen(willPayload), true, 1);
  client_.print(willPayload);
  client_.endWill();

  if (client_.connect(host_, port_) == 1) {
    client_.subscribe(commandTopic_, 1);
    JsonDocument online;
    online["device_id"] = deviceId_ == nullptr ? "" : deviceId_;
    online["status"] = "ONLINE";
    char onlinePayload[96];
    if (serializeMqttJson(online, onlinePayload, sizeof(onlinePayload))) {
      publishStatus(onlinePayload);
    }
    reconnectDelayMs_ = MQTT_CONNECT_RETRY_MS;
    nextAttemptAt_ = now + reconnectDelayMs_;
    return;
  }

  Serial.print("MQTT: connect failed, error=");
  Serial.println(client_.connectError());
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
                               size_t length, bool retained, uint8_t qos) {
  if (!client_.connected() || topic == nullptr || payload == nullptr) {
    return false;
  }
  if (client_.beginMessage(topic, length, retained, qos, false) == 0) {
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
  if (!isSafeIdentifier(recordingId)) {
    return false;
  }
  JsonDocument start;
  start["device_id"] = deviceId_ == nullptr ? "" : deviceId_;
  start["recording_id"] = recordingId;
  start["sample_rate"] = sampleRate;
  start["channels"] = channels;
  start["bits_per_sample"] = bitsPerSample;
  start["format"] = "pcm_s16le";

  char payload[224];
  if (!serializeMqttJson(start, payload, sizeof(payload))) {
    return false;
  }
  return publish(audioStartTopic_, payload, false);
}

bool MqttManager::publishAudioChunk(const char* recordingId, uint32_t sequence,
                                    const int16_t* samples, size_t sampleCount) {
  if (!isSafeIdentifier(recordingId) || samples == nullptr || sampleCount == 0) {
    return false;
  }
  char topic[160];
  const int written = snprintf(topic, sizeof(topic), "esp32/%s/audio/chunk/%s/%lu",
                               deviceId_, recordingId,
                               static_cast<unsigned long>(sequence));
  if (written < 0 || static_cast<size_t>(written) >= sizeof(topic)) {
    return false;
  }
  return publishBytes(topic, reinterpret_cast<const uint8_t*>(samples),
                      sampleCount * sizeof(int16_t), false, 1);
}

bool MqttManager::publishAudioEnd(const char* recordingId, uint32_t totalChunks,
                                  uint32_t sampleCount) {
  if (!isSafeIdentifier(recordingId)) {
    return false;
  }
  JsonDocument end;
  end["device_id"] = deviceId_ == nullptr ? "" : deviceId_;
  end["recording_id"] = recordingId;
  end["total_chunks"] = totalChunks;
  end["sample_count"] = sampleCount;

  char payload[192];
  if (!serializeMqttJson(end, payload, sizeof(payload))) {
    return false;
  }
  return publish(audioEndTopic_, payload, false);
}

void MqttManager::receiveCommand(int messageSize) {
  if (messageSize < 0 || messageSize >= COMMAND_BUFFER_SIZE) {
    while (client_.available()) {
      client_.read();
    }
    JsonDocument error;
    error["device_id"] = deviceId_ == nullptr ? "" : deviceId_;
    error["error_code"] = "COMMAND_TOO_LARGE";
    error["message"] = "Command payload exceeds buffer";
    char errorPayload[192];
    if (serializeMqttJson(error, errorPayload, sizeof(errorPayload))) {
      publishError(errorPayload);
    }
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
