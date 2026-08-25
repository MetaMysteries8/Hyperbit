#pragma once
#include "MicroBit.h"

class WukongLights {
    codal::I2C &i2c;
    bool lastOk;

    bool write4(uint8_t reg, uint8_t value);

public:
    explicit WukongLights(codal::I2C &bus);

    bool breath();
    bool steady(uint8_t brightness);
    bool off();
    bool selfTest();
    bool ok() const { return lastOk; }
};
