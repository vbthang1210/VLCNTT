#ifndef WIFI_MANAGER_H
#define WIFI_MANAGER_H

#include <Arduino.h>

class WifiManager {
 public:
  void begin(const char* ssid, const char* password);
  void update();
  bool isConnected() const;

 private:
  const char* ssid_ = nullptr;
  const char* password_ = nullptr;
  uint32_t nextAttemptAt_ = 0;
  uint8_t retryStep_ = 0;
  bool started_ = false;

  void scheduleReconnect(uint32_t now);
};

#endif
