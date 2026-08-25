#include "WukongLights.h"
#include "CodalFiber.h"

using namespace codal;
static const uint16_t WUKONG_I2C_ADDR = 0x20;

void WukongLights::write4(uint8_t reg, uint8_t value) {
    uint8_t b[4] = {reg, value, 0, 0};
    i2c.write(WUKONG_I2C_ADDR, b, 4);
}

void WukongLights::breath() {
    write4(0x11, 0);
    fiber_sleep(100);
    write4(0x12, 150);
}

void WukongLights::steady(uint8_t brightness) {
    if (brightness > 100) brightness = 100;
    write4(0x12, brightness);
    fiber_sleep(100);
    write4(0x11, 160);
}

void WukongLights::off() {
    write4(0x12, 0);
    fiber_sleep(100);
    write4(0x11, 160);
}
