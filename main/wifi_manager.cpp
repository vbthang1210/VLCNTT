#include "wifi_manager.h"

#include <WiFi.h>

namespace {
constexpr uint32_t kReconnectDelaysMs[] = {1000, 2000, 4000, 8000, 10000};
constexpr size_t kReconnectDelayCount =
    sizeof(kReconnectDelaysMs) / sizeof(kReconnectDelaysMs[0]);
}

void WifiManager::begin(const char* ssid, const char* password) {
  ssid_ = ssid;
  password_ = password;
  retryStep_ = 0;
  nextAttemptAt_ = 0;
  started_ = true;
  WiFi.mode(WIFI_STA);
}

void WifiManager::update() {
  if (!started_ || isConnected()) {
    return;
  }

  const uint32_t now = millis();
  if (static_cast<int32_t>(now - nextAttemptAt_) < 0) {
    return;
  }

  WiFi.begin(ssid_, password_);
  Serial.println("WiFi: connection attempt started");
  scheduleReconnect(now);
}

bool WifiManager::isConnected() const {
  return WiFi.status() == WL_CONNECTED;
}

void WifiManager::scheduleReconnect(uint32_t now) {
  const size_t step = retryStep_ < kReconnectDelayCount
                          ? retryStep_
                          : kReconnectDelayCount - 1;
  nextAttemptAt_ = now + kReconnectDelaysMs[step];
  if (retryStep_ < kReconnectDelayCount - 1) {
    ++retryStep_;
  }
}
