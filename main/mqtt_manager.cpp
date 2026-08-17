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
  if (!client_.connected() || topic == nullptr || payload == nullptr) {
    return false;
  }
  const size_t length = strlen(payload);
  if (client_.beginMessage(topic, length, retained, 1, false) == 0) {
    return false;
  }
  client_.print(payload);
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
