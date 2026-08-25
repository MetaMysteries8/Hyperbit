# HyperBit Info

HyperBit is a PC-hosted voice AI agent with a **BBC micro:bit V2 + ELECFREAKS Wukong** as its physical wireless body.

## micro:bit V2

- Gold capacitive logo = push-to-talk.
- Built-in microphone = speech capture.
- Built-in speaker = spoken responses.
- A = interrupt/cancel.
- B = replay.
- A+B = mute toggle.
- BLE = bidirectional compressed audio/control over Nordic UART Service.

The microphone hardware is activated only while the gold logo is held.

## Wukong

Wukong is actively driven by the firmware rather than merely serving as a battery holder:

- its built-in battery powers the handheld agent,
- eight blue base LEDs are controlled by Wukong's I2C controller,
- four Rainbow LEDs on P16 show agent-state colors,
- boot performs a visible Wukong self-test.

The Rainbow LEDs now use CODAL's hardware NeoPixel implementation. On micro:bit V2 that path uses NRF PWM2 and does not mask interrupts around WS2812 timing. Speaker audio uses NRF PWM1, so live state colors no longer require the old BLE-hostile bit-banging routine.

## Windows PC

The PC is the agent's main home:

- faster-whisper for local speech-to-text,
- Charm Hyper for the model/tool loop,
- durable memory and sandboxed workspace,
- Windows SAPI for local TTS,
- Bleak for Bluetooth.

The Hyper API key remains on the PC.

## BLE transport

HyperBit uses the standard Nordic UART Service UUID layout rather than the earlier custom three-characteristic `7f9a...` service. There are two application characteristics: NUS RX for PC -> device writes and NUS TX for device -> PC notifications.

BLE/GATT still exists underneath because it is the application-data mechanism exposed by the micro:bit SoftDevice and Windows BLE APIs, but HyperBit no longer invents a bespoke GATT shape.

The PC subscribes to NUS TX and sends a protocol HELLO. Firmware accepts HELLO only after notifications are enabled, then reports protocol version, firmware revision, and capability bits in READY. The current hardened firmware is protocol v2 / revision r3. The PC rejects stale firmware instead of silently attempting to debug an old HEX.

During a raw Bluetooth connection, the 5×5 display refresh driver is cleared and disabled. Firmware performs no face animation, accelerometer reads, Wukong updates, microphone work, speaker work, or button interaction until READY has successfully been queued. Connection setup gets priority over personality.

A half-open connection is evicted after about 45 seconds. After a valid session, an unexpected disconnect is surfaced to the Windows agent and normal voice mode automatically reconnects.

## Audio transport

Audio is 8 kHz mono IMA ADPCM.

Input is streamed in BLE-sized chunks while push-to-talk is held. The microphone ring is 512 bytes and is continuously drained rather than holding a whole utterance in RAM. The PC tracks packet sequence numbers and marks an utterance if a BLE packet gap occurs.

Output is segmented into <=512-byte ADPCM pieces, then each piece is packetized into <=20-byte NUS frames and acknowledged before the next piece is sent.

## Diagnostics

`TEST_BLE.bat` / `HyperBit.py --ble-test` tests only Bluetooth, NUS, the HyperBit HELLO/READY handshake, firmware revision/capabilities, and a short connection-stability window. It does **not** need a Hyper API key and does not load Whisper, call the model, or synthesize speech.

`BUILD_PROVENANCE.txt` in a release records the source/release side of the same identity story: exact GitHub commit, complete firmware-tree hash, key source hashes, requested and resolved CODAL versions, firmware revision, and real dynamic heap capacity extracted from the linked ELF.

## Release verification

Automatic releases are published only after the configured syntax checks, protocol/BLE regression tests, Bandit analysis, dependency vulnerability audit, ClamAV scans, successful micro:bit V2 firmware compilation, complete source-injection verification, BLE-security configuration verification, safe Rainbow-driver verification, and linked-ELF heap measurement complete.

Automated scanning and tests improve release hygiene but cannot prove that software contains no possible bug or malicious behavior.
