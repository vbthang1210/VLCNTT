#ifndef LED_MANAGER_H
#define LED_MANAGER_H

#include <Arduino.h>

class LedManager {
public:
    explicit LedManager(uint8_t pin);

    void begin();
    void turnOn();
    void turnOff();
    void setState(bool on);
    bool isOn() const;

private:
    uint8_t _pin;
    bool _isOn;
};

#endif
