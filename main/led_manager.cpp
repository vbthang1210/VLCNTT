#include "led_manager.h"

LedManager::LedManager(uint8_t pin)
    : _pin(pin),
      _isOn(false)
{
}

void LedManager::begin()
{
    pinMode(_pin, OUTPUT);

    // Trạng thái ban đầu: tắt LED
    turnOff();
}

void LedManager::turnOn()
{
    digitalWrite(_pin, HIGH);
    _isOn = true;
}

void LedManager::turnOff()
{
    digitalWrite(_pin, LOW);
    _isOn = false;
}

void LedManager::setState(bool on)
{
    if (on) {
        turnOn();
    } else {
        turnOff();
    }
}

bool LedManager::isOn() const
{
    return _isOn;
}