#ifndef MQTT_MANAGER_H
#define MQTT_MANAGER_H

#include <Arduino.h>
#include <WiFiClient.h>
#include <ArduinoMqttClient.h>

class MqttManager {
 public:
  using CommandCallback = void (*)(const char* payload, size_t length);

  MqttManager();
  void begin(const char* host, uint16_t port, const char* deviceId,
             const char* username, const char* password,
             CommandCallback callback);
  void update();
  bool isConnected();
  bool publishStatus(const char* payload);
  bool publishEvent(const char* payload);
  bool publishError(const char* payload);
  void receiveCommand(int messageSize);

 private:
  WiFiClient networkClient_;
  MqttClient client_;
  const char* host_ = nullptr;
  const char* deviceId_ = nullptr;
  const char* username_ = nullptr;
  const char* password_ = nullptr;
  char commandTopic_[96] = {};
  char statusTopic_[96] = {};
  char eventTopic_[96] = {};
  char errorTopic_[96] = {};
  CommandCallback callback_ = nullptr;
  uint32_t nextAttemptAt_ = 0;
  uint32_t reconnectDelayMs_ = 1000;
  uint16_t port_ = 1883;
  bool started_ = false;

  void connectIfDue();
  bool publish(const char* topic, const char* payload, bool retained);
};

#endif
