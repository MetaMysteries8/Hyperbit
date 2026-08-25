#include "WukongLights.h"
#include "CodalFiber.h"

using namespace codal;

// ELECFREAKS uses 7-bit address 0x10. CODAL's I2C API takes the 8-bit bus
// address, therefore the write address is 0x20.
static const uint16_t WUKONG_I2C_ADDR = 0x20;

WukongLights::WukongLights(I2C &bus) : i2c(bus), lastOk(true) {
    i2c.setFrequency(100000);
}

bool WukongLights::write4(uint8_t reg, uint8_t value) {
    uint8_t b[4] = {reg, value, 0, 0};
    lastOk = (i2c.write(WUKONG_I2C_ADDR, b, 4) == DEVICE_OK);
    return lastOk;
}

bool WukongLights::breath() {
    bool a = write4(0x11, 0);
    fiber_sleep(100);
    bool b = write4(0x12, 150);
    lastOk = a && b;
    return lastOk;
}

bool WukongLights::steady(uint8_t brightness) {
    if (brightness > 100) brightness = 100;
    bool a = write4(0x12, brightness);
    fiber_sleep(100);
    bool b = write4(0x11, 160);
    lastOk = a && b;
    return lastOk;
}

bool WukongLights::off() {
    bool a = write4(0x12, 0);
    fiber_sleep(100);
    bool b = write4(0x11, 160);
    lastOk = a && b;
    return lastOk;
}

bool WukongLights::selfTest() {
    bool ok1 = off();
    bool ok2 = steady(100);
    fiber_sleep(140);
    bool ok3 = off();
    fiber_sleep(80);
    bool ok4 = breath();
    lastOk = ok1 && ok2 && ok3 && ok4;
    return lastOk;
}
