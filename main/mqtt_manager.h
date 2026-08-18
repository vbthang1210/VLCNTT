#ifndef MQTT_MANAGER_H
#define MQTT_MANAGER_H

#include <Arduino.h>
#include <ArduinoMqttClient.h>
#include <WiFiClient.h>

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

  bool publishAudioStart(const char* payload);
  bool publishAudioData(const uint8_t* payload, size_t length);
  bool publishAudioEnd(const char* payload);

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
  char audioStartTopic_[96] = {};
  char audioDataTopic_[96] = {};
  char audioEndTopic_[96] = {};

  CommandCallback callback_ = nullptr;
  uint32_t nextAttemptAt_ = 0;
  uint32_t reconnectDelayMs_ = 1000;
  uint16_t port_ = 1883;
  bool started_ = false;

  void connectIfDue();
  bool publishText(const char* topic, const char* payload,
                   bool retained, int qos);
  bool publishBytes(const char* topic, const uint8_t* payload,
                    size_t length, bool retained, int qos);
};

#endif
