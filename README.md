# HyperBit

[![Build, Scan & Release HyperBit](https://github.com/MetaMysteries8/Hyperbit/actions/workflows/build-firmware.yml/badge.svg)](https://github.com/MetaMysteries8/Hyperbit/actions/workflows/build-firmware.yml)

A physical voice AI agent with a **BBC micro:bit V2 + ELECFREAKS Wukong** as its wireless body and a **Windows PC** as its main home/brain.

## Download

Use the latest GitHub Release and download `HyperBit-release.zip`. The release is created automatically only after firmware compilation, regression tests, provenance checks, and the configured security gates pass.

Keep the `HyperBit.hex` and PC files from the **same release** together. The PC validates both firmware revision and required transport capabilities so an accidentally flashed old HEX is reported directly.

## Quick start

1. Extract the whole release ZIP.
2. Plug the micro:bit V2 itself into USB and run `FLASH_FIRMWARE.bat`.
3. Run `TEST_BLE.bat` first. It needs no Hyper API key and verifies BLE/NUS/firmware identity.
4. Run `RUN_HYPERBIT.bat`; on first normal run it creates private `config.cmd` for your Hyper key.
5. Run `RUN_HYPERBIT.bat` again for full voice mode.

## Hardware budget

micro:bit V2 uses Nordic's **nRF52833**: a 64 MHz Cortex-M4F with **512 KiB flash and 128 KiB RAM**. HyperBit treats that as a shared embedded budget for CODAL, SoftDevice reservations, application heap/stack, buffers, and peripherals rather than assuming desktop-class resources.

The on-disk size of `HyperBit.hex` is not the linked application flash usage. Intel HEX is an ASCII container and the release image contains non-application regions required by the micro:bit. Each release's `BUILD_PROVENANCE.txt` records the real linked application flash/static-RAM/heap measurements.

## What the physical device does

The **V2 gold capacitive logo at the top** is push-to-talk. The microphone hardware is deactivated at rest, activated while the logo is held, and deactivated again on release.

Controls:

- **Hold gold logo:** microphone ON; stream compressed speech to the PC.
- **Release gold logo:** microphone OFF; finish the utterance.
- **A:** cancel/interrupt the current response.
- **B:** replay the last spoken answer.
- **A+B:** mute/unmute speaker output.

Audio is 8 kHz mono IMA ADPCM. Mic audio streams through a 512-byte ring rather than storing a whole utterance. TTS is split into acknowledged <=512-byte ADPCM segments and then into BLE-sized frames.

## Wukong is part of the device

The firmware actively uses Wukong rather than treating it only as a battery holder:

- Wukong battery provides wireless power.
- Eight blue base LEDs are controlled through Wukong's I2C light controller.
- Four Rainbow LEDs on **P16** display agent-state colors.
- Boot runs a Wukong self-test: base-light changes plus red -> green -> blue -> white on the Rainbow LEDs.

The Rainbow LEDs use CODAL's hardware NeoPixel/PWM path, not the older interrupt-masking bit-banger, so live state colors can coexist with BLE.

## BLE transport

HyperBit uses the conventional **Nordic UART Service (NUS)** UUID layout with a compact framed protocol on top for control, microphone audio, and TTS.

BLE still uses GATT underneath because that is the application-data mechanism provided by the micro:bit SoftDevice and Windows BLE APIs. The project no longer uses its old bespoke `7f9a...` three-characteristic service.

A usable session requires:

```text
raw BLE connection
  -> NUS discovery
  -> PC enables TX notifications
  -> PC HELLO
  -> firmware READY(protocol, firmware revision, capabilities)
  -> PC validates identity
```

Current hardened firmware is **protocol v2 / revision r5**. Revision r5 adds bounded half-open-link recovery on top of the buffered-notification transport introduced in r4.

At 8 kHz / 4-bit IMA ADPCM, the microphone produces about 4,000 compressed bytes per second. Protocol-v2 frames carry 17 audio bytes each, requiring roughly 236 notifications per second while speaking. Nordic S113 defaults to only one queued server notification, so the build configures a **12-entry GATTS notification queue** and reserves additional lower RAM for the SoftDevice before it is enabled. The 512-byte microphone ring remains a second backpressure layer.

During raw connection/GATT setup, r5 **freezes the currently rendered 5x5 frame without disabling CODAL's LED-matrix driver**. It schedules no new face animation, accelerometer reads, Wukong writes, microphone work, speaker work, or button processing until READY has successfully been queued. This preserves connection isolation while keeping the V2 TIMER4 display lifecycle stable.

A half-open raw connection is bounded: firmware gives Windows roughly 38 seconds for its 35-second GATT window, requests a GAP disconnect, and then gives the SoftDevice about two seconds to report the disconnect. If the link still claims to exist, r5 resets the MCU/SoftDevice so the board cannot remain trapped forever. The PC then rescans and reacquires a fresh Windows BLEDevice before retrying rather than repeatedly reusing the object associated with the failed GATT session.

Routine animation is now 25 Hz and the accelerometer is sampled only for disconnected/idle fluid states. This preserves the five-particle fluid effect while reducing unnecessary peripheral/scheduler work on the 64 MHz MCU.

Once a voice session has been validated, an unexpected disconnect is detected by the PC agent and automatically retried instead of leaving the program stuck waiting forever.

## BLE-only diagnostics

Run:

```text
TEST_BLE.bat
```

or:

```text
py -3 HyperBit.py --ble-test
```

This does **not** require a Hyper API key and does not load Whisper, call Hyper, or synthesize speech. It validates only Bluetooth/NUS, HELLO/READY, firmware version/capabilities, and a short stability window.

## PC side

The Windows PC handles:

- faster-whisper local speech-to-text,
- Charm Hyper model/tool calls,
- durable agent memory and sandboxed workspace,
- Windows SAPI TTS,
- BLE/NUS transport using Bleak.

The Hyper API key stays on the PC and `config.cmd` is intentionally excluded from version control/releases.

## Reproducible CODAL transport override

The queue/RAM change is not a hand-edited generated artifact. `firmware/codal_overrides.json` pins the reviewed CODAL commit and transport values, and `firmware/apply_codal_overrides.py` patches the freshly configured official CODAL tree only when its revision and expected source anchors match.

Both local `BUILD_FIRMWARE.bat` and GitHub Actions configure CODAL first, apply this override second, and compile third. The automatic release then verifies the patched manager/linker hashes and the application-data boundary in the final ELF.

## Release gates and provenance

Before an automatic release is published, GitHub Actions must successfully complete:

- Python syntax checking,
- protocol/BLE/transport regression unit tests,
- Bandit static analysis,
- pip-audit dependency vulnerability checking,
- ClamAV source scanning,
- exact HyperBit source/config injection verification,
- locked CODAL revision + fail-closed transport override verification,
- a verified 12-entry SoftDevice notification queue,
- reserved application-RAM/NOINIT boundary verification,
- BLE open-link security configuration verification,
- a guard preventing IRQ-masking Rainbow code,
- GNU Arm/CODAL firmware compilation,
- final-ELF application-boundary verification,
- real CODAL heap-capacity verification with a 64 KiB minimum,
- ClamAV scanning of the final HEX/ZIP,
- SHA-256 checksum generation.

`BUILD_PROVENANCE.txt` records the exact build commit, complete firmware-tree hash, key source hashes, firmware revision, resolved CODAL commit, transport queue/RAM settings, patched CODAL hashes, and actual dynamic heap capacity. This is how the release proves which source and transport configuration produced the HEX.

Automated checks reduce risk but cannot prove the absence of every possible software defect or malicious behavior. Hardware BLE/audio behavior must still be validated on the actual device.

See `INSTRUCTIONS.md` for setup/troubleshooting, `INFO.md` for architecture, `README_WINDOWS.md` for Windows details, and `PROTOCOL.md` for the wire protocol.
