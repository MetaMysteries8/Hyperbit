#include "ImaAdpcm.h"

static const int STEP_TABLE[89] = {
    7,8,9,10,11,12,13,14,16,17,19,21,23,25,28,31,
    34,37,41,45,50,55,60,66,73,80,88,97,107,118,130,143,
    157,173,190,209,230,253,279,307,337,371,408,449,494,544,
    598,658,724,796,876,963,1060,1166,1282,1411,1552,1707,1878,2066,
    2272,2499,2749,3024,3327,3660,4026,4428,4871,5358,5894,6484,7132,7845,
    8630,9493,10442,11487,12635,13899,15289,16818,18500,20350,22385,24623,
    27086,29794,32767
};

static const int INDEX_TABLE[16] = {
    -1,-1,-1,-1,2,4,6,8,
    -1,-1,-1,-1,2,4,6,8
};

static int clamp16(int v) {
    if (v < -32768) return -32768;
    if (v > 32767) return 32767;
    return v;
}

uint8_t ImaAdpcmState::encode(int16_t sample) {
    int step = STEP_TABLE[index];
    int diff = (int)sample - predictor;
    int nibble = 0;
    if (diff < 0) { nibble = 8; diff = -diff; }
    int delta = 0;
    int vpdiff = step >> 3;
    if (diff >= step) { delta |= 4; diff -= step; vpdiff += step; }
    if (diff >= (step >> 1)) { delta |= 2; diff -= step >> 1; vpdiff += step >> 1; }
    if (diff >= (step >> 2)) { delta |= 1; vpdiff += step >> 2; }
    nibble |= delta;
    predictor = clamp16(predictor + ((nibble & 8) ? -vpdiff : vpdiff));
    index += INDEX_TABLE[nibble & 0x0F];
    if (index < 0) index = 0;
    if (index > 88) index = 88;
    return (uint8_t)nibble;
}

int16_t ImaAdpcmState::decode(uint8_t nibble) {
    nibble &= 0x0F;
    int step = STEP_TABLE[index];
    int diff = step >> 3;
    if (nibble & 4) diff += step;
    if (nibble & 2) diff += step >> 1;
    if (nibble & 1) diff += step >> 2;
    predictor = clamp16(predictor + ((nibble & 8) ? -diff : diff));
    index += INDEX_TABLE[nibble];
    if (index < 0) index = 0;
    if (index > 88) index = 88;
    return (int16_t)predictor;
}
