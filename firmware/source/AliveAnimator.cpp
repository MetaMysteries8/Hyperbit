#include "AliveAnimator.h"

using namespace codal;

static int clampi(int v, int lo, int hi) {
    if (v < lo) return lo;
    if (v > hi) return hi;
    return v;
}

AliveAnimator::AliveAnimator(MicroBit &microbit, WukongLights &baseLights, WukongRainbow &rainbowLights) :
    bit(microbit),
    base(baseLights),
    rainbow(rainbowLights),
    stateValue(PHYS_DISCONNECTED),
    inputLevelValue(0),
    outputLevelValue(0),
    mutedValue(false),
    frame(0),
    baseDivider(0),
    lastBaseLevel(255),
    baseDynamic(false)
{
    // Start the five particles spread around the face.
    const int16_t sx[5] = {256, 768, 512, 128, 896};
    const int16_t sy[5] = {256, 256, 512, 832, 832};
    for (int i = 0; i < 5; ++i) {
        px[i] = sx[i];
        py[i] = sy[i];
        vx[i] = 0;
        vy[i] = 0;
    }

    bit.display.setDisplayMode(DISPLAY_MODE_GREYSCALE);
    bit.display.setBrightness(255);
    bit.display.clear();
}

void AliveAnimator::setState(uint8_t state) {
    if (stateValue == state)
        return;

    stateValue = state;
    inputLevelValue = 0;
    outputLevelValue = 0;
    baseDynamic = false;
    baseDivider = 0;
    lastBaseLevel = 255;

    if (state == PHYS_DISCONNECTED) {
        base.breath();
    } else {
        // Enter steady mode once; subsequent animation frames only update the
        // brightness register, avoiding the old 100 ms pause every frame.
        base.steady(18);
        baseDynamic = true;
    }
}

void AliveAnimator::clearMatrix() {
    bit.display.image.clear();
}

void AliveAnimator::plot(int x, int y, uint8_t value) {
    if (x < 0 || x > 4 || y < 0 || y > 4 || value == 0)
        return;

    int old = bit.display.image.getPixelValue(x, y);
    int next = old + value;
    if (next > 255) next = 255;
    bit.display.image.setPixelValue(x, y, next);
}

void AliveAnimator::renderFluid(int ax, int ay, bool dimmer) {
    clearMatrix();

    // The board reports acceleration in milli-g. Turn that into a gentle
    // gravity vector. The Y sign is inverted to match display coordinates.
    int gx = clampi(ax / 52, -20, 20);
    int gy = clampi(-ay / 52, -20, 20);

    for (int i = 0; i < 5; ++i) {
        vx[i] += gx;
        vy[i] += gy;

        // Tiny deterministic swirl keeps the blob alive even when perfectly flat.
        vx[i] += ((int)((frame + i * 7) % 11) - 5) / 2;
        vy[i] += ((int)((frame * 3 + i * 5) % 9) - 4) / 2;

        // Fluid-ish drag.
        vx[i] = (vx[i] * 29) / 32;
        vy[i] = (vy[i] * 29) / 32;

        px[i] += vx[i];
        py[i] += vy[i];

        const int16_t minP = 40;
        const int16_t maxP = 4 * 256 - 40;
        if (px[i] < minP) { px[i] = minP; vx[i] = -vx[i] / 2; }
        if (px[i] > maxP) { px[i] = maxP; vx[i] = -vx[i] / 2; }
        if (py[i] < minP) { py[i] = minP; vy[i] = -vy[i] / 2; }
        if (py[i] > maxP) { py[i] = maxP; vy[i] = -vy[i] / 2; }

        int x = (px[i] + 128) >> 8;
        int y = (py[i] + 128) >> 8;
        uint8_t main = dimmer ? 105 : 170;
        uint8_t halo = dimmer ? 24 : 40;

        plot(x, y, main);
        plot(x - 1, y, halo);
        plot(x + 1, y, halo);
        plot(x, y - 1, halo);
        plot(x, y + 1, halo);
    }
}

void AliveAnimator::renderListening(uint8_t level) {
    clearMatrix();
    int pulse = clampi(level, 0, 255);
    int core = 150 + pulse / 3;
    int ring = 28 + pulse / 2;

    // Compact center mass.
    plot(2, 2, core);
    plot(2, 1, 95 + pulse / 3);
    plot(2, 3, 95 + pulse / 3);
    plot(1, 2, 95 + pulse / 3);
    plot(3, 2, 95 + pulse / 3);

    // Voice energy makes the blob breathe outward.
    if (pulse > 45) {
        plot(1, 1, ring);
        plot(3, 1, ring);
        plot(1, 3, ring);
        plot(3, 3, ring);
    }
    if (pulse > 120) {
        plot(2, 0, ring);
        plot(4, 2, ring);
        plot(2, 4, ring);
        plot(0, 2, ring);
    }
}

void AliveAnimator::renderThinking() {
    clearMatrix();
    static const uint8_t path[12][2] = {
        {2,0},{3,0},{4,1},{4,2},{4,3},{3,4},
        {2,4},{1,4},{0,3},{0,2},{0,1},{1,0}
    };

    int head = (frame / 2) % 12;
    for (int trail = 0; trail < 5; ++trail) {
        int idx = (head - trail + 12) % 12;
        uint8_t b = (uint8_t)(220 - trail * 42);
        plot(path[idx][0], path[idx][1], b);
    }
    plot(2, 2, 22);
}

void AliveAnimator::renderSpeaking(uint8_t level) {
    clearMatrix();
    int pulse = clampi(level, 0, 255);
    int wobble = ((frame / 2) & 1) ? 1 : 0;

    // Different silhouette from listening: a soft horizontal two-lobed "voice" blob.
    plot(1, 2, 120 + pulse / 3);
    plot(3, 2, 120 + pulse / 3);
    plot(2, 2, 65 + pulse / 4);
    plot(1, 1 + wobble, 50 + pulse / 3);
    plot(3, 2 - wobble, 50 + pulse / 3);

    if (pulse > 55) {
        plot(0, 2, 30 + pulse / 2);
        plot(4, 2, 30 + pulse / 2);
    }
    if (pulse > 135) {
        plot(1, 0, 36 + pulse / 3);
        plot(3, 4, 36 + pulse / 3);
    }
}

void AliveAnimator::renderBusyPulse() {
    clearMatrix();
    int phase = frame % 24;
    int d = phase < 12 ? phase : 24 - phase;
    uint8_t b = (uint8_t)(55 + d * 12);
    plot(2, 2, b);
    plot(1, 2, b / 2);
    plot(3, 2, b / 2);
    plot(2, 1, b / 2);
    plot(2, 3, b / 2);
}

void AliveAnimator::renderError() {
    clearMatrix();
    uint8_t b = ((frame / 5) & 1) ? 240 : 80;
    for (int i = 0; i < 5; ++i) {
        plot(i, i, b);
        plot(4 - i, i, b);
    }
}

void AliveAnimator::updateBodyGlow(uint8_t level) {
    if (stateValue == PHYS_DISCONNECTED || !baseDynamic)
        return;

    // I2C body glow only updates every ~120 ms when tick() runs around 30 ms.
    if (++baseDivider < 4)
        return;
    baseDivider = 0;

    int wave = (int)(frame % 32);
    if (wave > 16) wave = 32 - wave;

    int target = 16;
    switch (stateValue) {
        case PHYS_IDLE: target = 18 + wave; break;
        case PHYS_LISTENING: target = 24 + level / 4; break;
        case PHYS_UPLOADING: target = 35 + wave * 2; break;
        case PHYS_TRANSCRIBING: target = 40 + wave; break;
        case PHYS_THINKING: target = 42 + wave * 2; break;
        case PHYS_SPEAKING: target = 28 + level / 4; break;
        case PHYS_ERROR: target = 90; break;
        case PHYS_MUTED: target = 10 + wave / 2; break;
        default: target = 16; break;
    }
    target = clampi(target, 0, 100);

    if (lastBaseLevel == 255 || (target > lastBaseLevel ? target - lastBaseLevel : lastBaseLevel - target) >= 2) {
        base.setBrightnessFast((uint8_t)target);
        lastBaseLevel = (uint8_t)target;
    }
}

void AliveAnimator::renderWukong(int ax, int ay, uint8_t level) {
    int xbias = clampi(128 + ax / 8, 0, 255);
    int ybias = clampi(128 - ay / 8, 0, 255);

    switch (stateValue) {
        case PHYS_DISCONNECTED:
        case PHYS_IDLE: {
            // Four LEDs form a little pool whose brightest corner follows gravity.
            int weights[4] = {
                (255 - xbias) + (255 - ybias),
                xbias + (255 - ybias),
                (255 - xbias) + ybias,
                xbias + ybias
            };
            for (int i = 0; i < 4; ++i) {
                int b = 3 + weights[i] / 30;
                if (stateValue == PHYS_DISCONNECTED) b /= 2;
                rainbow.setPixel(i, 0, (uint8_t)(b + 4), (uint8_t)(b + 12));
            }
            rainbow.show();
            break;
        }

        case PHYS_LISTENING: {
            int b = 8 + level / 10;
            for (int i = 0; i < 4; ++i)
                rainbow.setPixel(i, 0, (uint8_t)(b + 8), (uint8_t)(b + 12));
            rainbow.show();
            break;
        }

        case PHYS_THINKING: {
            int head = (frame / 3) & 3;
            for (int i = 0; i < 4; ++i) {
                int d = (i - head + 4) & 3;
                uint8_t b = d == 0 ? 28 : (d == 1 ? 10 : 3);
                rainbow.setPixel(i, b / 2, 0, b);
            }
            rainbow.show();
            break;
        }

        case PHYS_SPEAKING: {
            int b = 7 + level / 9;
            int wobble = (frame / 2) & 1;
            rainbow.setPixel(0, (uint8_t)(b / 2), (uint8_t)(b + 3), (uint8_t)(b + 7));
            rainbow.setPixel(3, (uint8_t)(b / 2), (uint8_t)(b + 3), (uint8_t)(b + 7));
            rainbow.setPixel(1, (uint8_t)(wobble ? b : b / 3), (uint8_t)(b / 2), (uint8_t)(b + 5));
            rainbow.setPixel(2, (uint8_t)(wobble ? b / 3 : b), (uint8_t)(b / 2), (uint8_t)(b + 5));
            rainbow.show();
            break;
        }

        case PHYS_ERROR:
            rainbow.setAll(28, 0, 0);
            break;
        case PHYS_MUTED:
            rainbow.setAll(10, 5, 0);
            break;
        case PHYS_UPLOADING:
        case PHYS_TRANSCRIBING:
        default: {
            int b = 5 + ((frame % 20) < 10 ? frame % 10 : 20 - (frame % 20));
            rainbow.setAll((uint8_t)(b / 2), 0, (uint8_t)(b + 8));
            break;
        }
    }
}

void AliveAnimator::tick() {
    ++frame;

    int ax = bit.accelerometer.getX();
    int ay = bit.accelerometer.getY();
    uint8_t activeLevel = stateValue == PHYS_LISTENING ? inputLevelValue : outputLevelValue;

    if (mutedValue && stateValue != PHYS_LISTENING && stateValue != PHYS_UPLOADING) {
        renderBusyPulse();
        renderWukong(ax, ay, 0);
        updateBodyGlow(0);
        return;
    }

    switch (stateValue) {
        case PHYS_DISCONNECTED: renderFluid(ax, ay, true); break;
        case PHYS_IDLE: renderFluid(ax, ay, false); break;
        case PHYS_LISTENING: renderListening(inputLevelValue); break;
        case PHYS_THINKING: renderThinking(); break;
        case PHYS_SPEAKING: renderSpeaking(outputLevelValue); break;
        case PHYS_ERROR: renderError(); break;
        case PHYS_UPLOADING:
        case PHYS_TRANSCRIBING:
        default: renderBusyPulse(); break;
    }

    renderWukong(ax, ay, activeLevel);
    updateBodyGlow(activeLevel);
}
