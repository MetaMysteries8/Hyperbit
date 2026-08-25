#pragma once
#include "MicroBit.h"

class WukongRainbow {
    codal::Pin &pin;
    uint8_t pixels[12];

public:
    explicit WukongRainbow(codal::Pin &dataPin);

    void clear();
    void setPixel(int index, uint8_t r, uint8_t g, uint8_t b);
    void setAll(uint8_t r, uint8_t g, uint8_t b);
    void show();
    void state(uint8_t state);
    void selfTest();
};
