#include "WukongRainbow.h"
#include "CodalFiber.h"
#include "neopixel.h"
#include <string.h>

using namespace codal;

WukongRainbow::WukongRainbow(Pin &dataPin) : pin(dataPin) {
    memset(pixels, 0, sizeof(pixels));
}

void WukongRainbow::show() {
    // micro:bit V2 enables HARDWARE_NEOPIXEL in CODAL. That implementation uses
    // NRF_PWM2 instead of masking interrupts around a timing loop, so Rainbow
    // updates can coexist with the SoftDevice. Speaker audio uses NRF_PWM1.
    codal::neopixel_send_buffer(pin, pixels, sizeof(pixels));
}

void WukongRainbow::clear() {
    memset(pixels, 0, sizeof(pixels));
    show();
}

void WukongRainbow::setPixel(int index, uint8_t r, uint8_t g, uint8_t b) {
    if (index < 0 || index >= 4)
        return;

    // Wukong's MakeCode extension uses NeoPixelMode.RGB, which is GRB wire order.
    int o = index * 3;
    pixels[o + 0] = g;
    pixels[o + 1] = r;
    pixels[o + 2] = b;
}

void WukongRainbow::setAll(uint8_t r, uint8_t g, uint8_t b) {
    for (int i = 0; i < 4; ++i)
        setPixel(i, r, g, b);
    show();
}

void WukongRainbow::state(uint8_t state) {
    switch (state) {
        case 0: setAll(0, 0, 8); break;       // disconnected
        case 1: setAll(0, 10, 2); break;      // idle
        case 2: setAll(0, 18, 18); break;     // listening
        case 3: setAll(20, 8, 0); break;      // uploading
        case 4: setAll(10, 0, 20); break;     // transcribing
        case 5: setAll(20, 0, 20); break;     // thinking
        case 6: setAll(18, 18, 18); break;    // speaking
        case 7: setAll(24, 0, 0); break;      // error
        case 8: setAll(12, 8, 0); break;      // muted
        default: clear(); break;
    }
}

void WukongRainbow::selfTest() {
    setAll(18, 0, 0);
    fiber_sleep(90);
    setAll(0, 18, 0);
    fiber_sleep(90);
    setAll(0, 0, 18);
    fiber_sleep(90);
    setAll(10, 10, 10);
    fiber_sleep(90);
    clear();
}
