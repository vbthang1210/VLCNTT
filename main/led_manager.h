#ifndef LED_MANAGER_H
#define LED_MANAGER_H

#include <Arduino.h>

class LedManager {
 public:
  explicit LedManager(uint8_t pin);
  void begin();
  void turnOn();
  void turnOff();
  bool isOn() const;

 private:
  uint8_t pin_;
  bool isOn_ = false;
};

#endif
