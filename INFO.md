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

The Rainbow LEDs use CODAL's hardware NeoPixel implementation. On micro:bit V2 that path uses NRF PWM2 and does not mask interrupts around WS2812 timing. Speaker audio uses NRF PWM1, so live state colors do not require the old BLE-hostile bit-banging routine.

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

The PC subscribes to NUS TX and sends a protocol HELLO. Firmware accepts HELLO only after notifications are enabled, then reports protocol version, firmware revision, and capability bits in READY. The current hardened firmware is protocol v2 / revision r4. The PC requires the buffered-HVN capability and rejects stale firmware instead of silently attempting to debug an old HEX.

During a raw Bluetooth connection, the 5×5 display refresh driver is cleared and disabled. Firmware performs no face animation, accelerometer reads, Wukong updates, microphone work, speaker work, or button interaction until READY has successfully been queued. Connection setup gets priority over personality.

A half-open connection is evicted after about 45 seconds. After a valid session, an unexpected disconnect is surfaced to the Windows agent and normal voice mode automatically reconnects.

## Audio transport

Audio is 8 kHz mono IMA ADPCM.

Input is streamed in BLE-sized chunks while push-to-talk is held. At 4 bits per sample this produces about 4,000 compressed bytes per second. Protocol v2 carries up to 17 audio bytes in each 20-byte NUS notification, so continuous input needs roughly 236 notifications per second.

The Nordic S113 default server-notification queue is only one entry. Firmware r4's reproducible build therefore applies a reviewed **12-entry GATTS notification queue** before the SoftDevice is enabled and reserves additional lower nRF52833 RAM for that configuration. The 512-byte microphone ring is retained as a second backpressure layer. Temporary queue exhaustion is retried; a sustained transport/ring overflow is explicitly reported with the utterance.

Output is segmented into <=512-byte ADPCM pieces, then each piece is packetized into <=20-byte NUS frames and acknowledged before the next piece is sent.

## Build integrity

`firmware/codal_overrides.json` defines the reviewed CODAL revision, notification-queue size, application-RAM boundary, NOINIT boundary, and stack reservation. `firmware/apply_codal_overrides.py` refuses to patch an unexpected CODAL revision or source layout.

The automatic build configures a clean official `microbit-v2-samples` tree, applies that override between CMake configuration and compilation, then verifies the exact patched manager/linker inputs and linked application boundary. A release also fails if calculated CODAL heap capacity falls below 64 KiB.

This is intentionally stricter than merely seeing `MICROBIT.hex` exist: it makes stale generated build trees and silent upstream layout changes release-blocking conditions.

## Diagnostics

`TEST_BLE.bat` / `HyperBit.py --ble-test` tests only Bluetooth, NUS, the HyperBit HELLO/READY handshake, firmware revision/capabilities, and a short connection-stability window. It does **not** need a Hyper API key and does not load Whisper, call the model, or synthesize speech.

`BUILD_PROVENANCE.txt` in a release records the source/release side of the same identity story: exact GitHub commit, complete firmware-tree hash, key source hashes, requested and resolved CODAL versions, firmware revision, HVN queue size, application RAM origin, patched CODAL hashes, and real dynamic heap capacity extracted from the linked ELF.

## Release verification

Automatic releases are published only after the configured syntax checks, protocol/BLE regression tests, Bandit analysis, dependency vulnerability audit, ClamAV scans, successful micro:bit V2 firmware compilation, complete source-injection verification, locked-CODAL/override verification, BLE-security configuration verification, safe Rainbow-driver verification, linked application-boundary verification, and linked-ELF heap measurement complete.

Automated scanning and tests improve release hygiene but cannot prove that software contains no possible bug or malicious behavior. Physical BLE/audio behavior still has to be validated on the actual micro:bit/Wukong hardware.
