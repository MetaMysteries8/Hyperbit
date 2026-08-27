#include "MicroBit.h"

using namespace codal;

MicroBit uBit;
MicroBitUARTService *uart = nullptr;

static void onConnected(MicroBitEvent)
{
    uBit.display.print("C");
}

static void onDisconnected(MicroBitEvent)
{
    uBit.display.print("D");
}

int main()
{
    // Deliberately mirror Lancaster's BLE sample lifecycle: initialize the
    // micro:bit first, then construct the upstream UART service directly.
    uBit.init();

    uBit.messageBus.listen(MICROBIT_ID_BLE, MICROBIT_BLE_EVT_CONNECTED, onConnected);
    uBit.messageBus.listen(MICROBIT_ID_BLE, MICROBIT_BLE_EVT_DISCONNECTED, onDisconnected);

    // No HyperBit subclass, custom UUID registration, notification queue patch,
    // microphone, speaker, Wukong driver, protocol parser, or watchdog exists in
    // this diagnostic image. This is CODAL MicroBitUARTService itself.
    uart = new MicroBitUARTService(*uBit.ble, 32, 32);

    // U = booted and UART service constructed. C/D are connection events.
    uBit.display.print("U");

    release_fiber();
    return 0;
}
