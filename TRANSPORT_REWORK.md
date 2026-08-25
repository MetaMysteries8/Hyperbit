# HyperBit transport rework

This branch replaces the original three-characteristic HyperBit BLE service with a minimal Nordic UART Service layout and reduces runtime buffering pressure.

Key motivations observed on physical hardware:

- Windows could establish a raw BLE link but repeatedly timed out during service discovery.
- The micro:bit display appeared to freeze during the connection window.
- The Nordic SDK build emitted a warning showing `MICROBIT_BLE_SECURITY_MODE` being redefined from open-link mode to MITM mode in one include path.
- The firmware used relatively large static audio buffers, so reducing them is still useful for increasing CODAL's dynamic heap capacity.

A note on the compiler's `RAM: 98.33%` line: this is **not** evidence that only ~2 KiB of heap remains. CODAL's nRF52833 SoftDevice linker script deliberately expands its `.heap` section to fill all RAM up to a fixed 0x800-byte stack reserve. The generic GNU memory-region percentage therefore remains near 98.33% even when static buffers are reduced. CI now extracts `__end__` from the linked ELF and calculates the actual heap capacity separately.

The rework therefore:

- uses the standard NUS service/RX/TX UUID layout,
- multiplexes HyperBit control, microphone and TTS frames over two characteristics,
- adds an explicit HELLO/READY application handshake,
- sets `MICROBIT_BLE_SECURITY_LEVEL` explicitly to `SECURITY_MODE_ENCRYPTION_OPEN_LINK`,
- reduces the TTS segment buffer from 4096 bytes to 512 bytes,
- reduces the microphone ring buffer from 1024 bytes to 512 bytes,
- disables the LED matrix refresh driver and all peripheral animation/work during raw BLE connection setup,
- makes any BLE security-mode redefinition a release-blocking CI error,
- records exact source hashes, CODAL commit, and actual heap-capacity calculation in `BUILD_PROVENANCE.txt`.
