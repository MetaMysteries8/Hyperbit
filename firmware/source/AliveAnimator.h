#pragma once
#include "MicroBit.h"
#include "WukongLights.h"
#include "WukongRainbow.h"

enum HyperBitVisualState {
    PHYS_DISCONNECTED = 0,
    PHYS_IDLE = 1,
    PHYS_LISTENING = 2,
    PHYS_UPLOADING = 3,
    PHYS_TRANSCRIBING = 4,
    PHYS_THINKING = 5,
    PHYS_SPEAKING = 6,
    PHYS_ERROR = 7,
    PHYS_MUTED = 8,
    PHYS_CONNECTING = 9
};

class AliveAnimator {
    codal::MicroBit &bit;
    WukongLights &base;
    WukongRainbow &rainbow;

    uint8_t stateValue;
    uint8_t inputLevelValue;
    uint8_t outputLevelValue;
    bool mutedValue;
    uint32_t frame;
    uint8_t baseDivider;
    uint8_t lastBaseLevel;
    bool baseDynamic;

    // Fixed point positions/velocities: 256 units per LED cell.
    int16_t px[5];
    int16_t py[5];
    int16_t vx[5];
    int16_t vy[5];

    void clearMatrix();
    void plot(int x, int y, uint8_t value);
    void renderFluid(int ax, int ay, bool dimmer);
    void renderConnecting();
    void renderListening(uint8_t level);
    void renderThinking();
    void renderSpeaking(uint8_t level);
    void renderBusyPulse();
    void renderError();
    void renderWukong(int ax, int ay, uint8_t level);
    void updateBodyGlow(uint8_t level);

public:
    AliveAnimator(codal::MicroBit &microbit, WukongLights &baseLights, WukongRainbow &rainbowLights);

    void setState(uint8_t state);
    uint8_t state() const { return stateValue; }
    void setInputLevel(uint8_t level) { inputLevelValue = level; }
    void setOutputLevel(uint8_t level) { outputLevelValue = level; }
    void setMuted(bool muted) { mutedValue = muted; }

    void tick();
};
