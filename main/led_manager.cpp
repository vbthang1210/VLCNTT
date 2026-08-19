#include "led_manager.h"

LedManager::LedManager(uint8_t pin) : pin_(pin) {}

void LedManager::begin() {
  pinMode(pin_, OUTPUT);
  turnOff();
}

void LedManager::turnOn() {
  digitalWrite(pin_, HIGH);
  isOn_ = true;
}

void LedManager::turnOff() {
  digitalWrite(pin_, LOW);
  isOn_ = false;
}

bool LedManager::isOn() const {
  return isOn_;
}
