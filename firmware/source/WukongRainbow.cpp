#include "WukongRainbow.h"
#include "CodalFiber.h"
#include "nrf.h"
#include <string.h>

using namespace codal;

// Timing routine adapted from Microsoft PXT's MIT-licensed micro:bit NeoPixel
// implementation. It runs from RAM so flash wait states do not distort WS2812 timing.
extern "C" void __attribute__((long_call, section(".data")))
neopixel_send_buffer_nrf52(void *port500, uint32_t pinbr, const uint8_t *ptr, int numBytes);

WukongRainbow::WukongRainbow(Pin &dataPin) : pin(dataPin) {
    memset(pixels, 0, sizeof(pixels));
}

void WukongRainbow::show() {
    pin.setDigitalValue(0);
    fiber_sleep(1);

    auto port = pin.name < 32 ? NRF_P0 : NRF_P1;
    uint32_t pinAndBrightness = (pin.name & 31) | (0x100UL << 20);

    __disable_irq();
    neopixel_send_buffer_nrf52(
        (uint8_t *)(void *)port + 0x500,
        pinAndBrightness,
        pixels,
        sizeof(pixels)
    );
    __enable_irq();
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
        case 0: setAll(0, 0, 8); break;
        case 1: setAll(0, 10, 2); break;
        case 2: setAll(0, 18, 18); break;
        case 3: setAll(20, 8, 0); break;
        case 4: setAll(10, 0, 20); break;
        case 5: setAll(20, 0, 20); break;
        case 6: setAll(18, 18, 18); break;
        case 7: setAll(24, 0, 0); break;
        case 8: setAll(12, 8, 0); break;
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
