# Stock CODAL UART diagnostic

This diagnostic exists to separate HyperBit application code from the underlying CODAL/SoftDevice/Windows GATT path.

Both firmware images use the locked `codal-microbit-v2` v0.3.4 target and construct upstream `MicroBitUARTService` directly after `uBit.init()`. They contain no HyperBit BLE subclass, HELLO/READY protocol, Wukong code, microphone, speaker, half-open watchdog, custom SoftDevice notification queue, custom RAM reservation, or CODAL source patch.

## Images

- `CODAL-UART-OPEN.hex`: minimal UART service with the same open-link security policy used by HyperBit.
- `CODAL-UART-PAIRING.hex`: the same minimal UART service using CODAL pairing/no-MITM security instead of open-link security.

The 5x5 display shows `U` after the UART service is constructed, `C` on a BLE connection event, and `D` on disconnect.

## Test order

1. Flash `CODAL-UART-OPEN.hex`.
2. Run `TEST_STOCK_CODAL_BLE.bat` with no arguments.
3. If Windows still reports GATT `Unreachable`, flash `CODAL-UART-PAIRING.hex`.
4. Run `TEST_STOCK_CODAL_BLE.bat --pair` and accept any Windows pairing UI.

The diagnostic client does not send HyperBit HELLO. Success means Windows connected and returned the stock CODAL Nordic UART Service from GATT.

## Interpretation

- **OPEN passes:** HyperBit's remaining SoftDevice transport overrides/configuration are the next suspect.
- **OPEN fails, PAIRING passes:** open-link security/configuration is the likely fault line.
- **Both fail at GATT discovery:** the failure is below HyperBit's protocol/service implementation and points at the CODAL/SoftDevice/Windows/adapter/board interaction.
- **GATT discovery succeeds but NUS is absent:** inspect CODAL UUID/service configuration rather than HyperBit framing.
