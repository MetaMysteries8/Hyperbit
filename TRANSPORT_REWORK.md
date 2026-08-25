# HyperBit transport rework

This branch replaces the original three-characteristic HyperBit BLE service with a minimal Nordic UART Service layout and reduces firmware RAM pressure.

Key motivations observed on physical hardware:

- Windows could establish a raw BLE link but repeatedly timed out during service discovery.
- The micro:bit display appeared to freeze during the connection window.
- Build 28 used 120,768 / 122,816 bytes of application RAM (98.33%), leaving only about 2 KiB of headroom.
- The Nordic SDK build emitted a warning showing `MICROBIT_BLE_SECURITY_MODE` being redefined from open-link mode to MITM mode in one include path.

The rework therefore:

- uses the standard NUS service/RX/TX UUID layout,
- multiplexes HyperBit control, microphone and TTS frames over two characteristics,
- adds an explicit HELLO/READY application handshake,
- sets `MICROBIT_BLE_SECURITY_LEVEL` explicitly to `SECURITY_MODE_ENCRYPTION_OPEN_LINK`,
- reduces the TTS segment buffer from 4096 bytes to 512 bytes,
- reduces the microphone ring buffer from 1024 bytes to 512 bytes,
- disables the LED matrix refresh driver and all peripheral animation/work during raw BLE connection setup,
- makes any BLE security-mode redefinition a release-blocking CI error,
- records exact source hashes/CODAL commit/linker memory information in `BUILD_PROVENANCE.txt`.
