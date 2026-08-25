#pragma once
#include "MicroBit.h"

class WukongLights {
    codal::I2C &i2c;
    void write4(uint8_t reg, uint8_t value);
public:
    WukongLights(codal::I2C &bus) : i2c(bus) {}
    void breath();
    void steady(uint8_t brightness);
    void off();
};
