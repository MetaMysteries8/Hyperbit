#pragma once
#include <stdint.h>

class ImaAdpcmState {
public:
    int predictor;
    int index;

    ImaAdpcmState() : predictor(0), index(0) {}
    void reset() { predictor = 0; index = 0; }

    uint8_t encode(int16_t sample);
    int16_t decode(uint8_t nibble);
};
