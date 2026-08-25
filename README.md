# HyperBit

[![Build, Scan & Release HyperBit](https://github.com/MetaMysteries8/Hyperbit/actions/workflows/build-firmware.yml/badge.svg)](https://github.com/MetaMysteries8/Hyperbit/actions/workflows/build-firmware.yml)

A physical voice AI agent with a **BBC micro:bit V2 + ELECFREAKS Wukong** as its wireless body and a **Windows PC** as its main home/brain.

## Download

Use the latest GitHub Release and download `HyperBit-release.zip`. The release is created automatically only after firmware compilation, regression tests, provenance checks, and the configured security gates pass.

Keep the `HyperBit.hex` and PC files from the **same release** together. The PC now validates the firmware revision during connection so an accidentally flashed old HEX is reported directly.

## Quick start

1. Extract the whole release ZIP.
2. Plug the micro:bit V2 itself into USB and run `FLASH_FIRMWARE.bat`.
3. Run `TEST_BLE.bat` first. It needs no Hyper API key and verifies BLE/NUS/firmware identity.
4. Run `RUN_HYPERBIT.bat`; on first normal run it creates private `config.cmd` for your Hyper key.
5. Run `RUN_HYPERBIT.bat` again for full voice mode.

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

Current hardened firmware is **protocol v2 / revision r3**.

During the raw connection and handshake, the micro:bit's 5×5 display is intentionally **black**. Firmware disables display refresh and performs no animation, accelerometer reads, Wukong updates, microphone work, speaker work, or button processing until READY has successfully been queued. Connection setup gets exclusive priority.

Half-open raw connections are evicted after about 45 seconds. Once a voice session has been validated, an unexpected disconnect is detected by the PC agent and automatically retried instead of leaving the program stuck waiting forever.

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

## Release gates and provenance

Before an automatic release is published, GitHub Actions must successfully complete:

- Python syntax checking,
- protocol/BLE regression unit tests,
- Bandit static analysis,
- pip-audit dependency vulnerability checking,
- ClamAV source scanning,
- GNU Arm/CODAL firmware compilation,
- byte-for-byte verification of the complete injected firmware source tree,
- BLE open-link security configuration verification,
- a guard preventing IRQ-masking Rainbow code,
- real CODAL heap-capacity extraction from the linked ELF,
- ClamAV scanning of the final HEX/ZIP,
- SHA-256 checksum generation.

`BUILD_PROVENANCE.txt` records the exact build commit, complete firmware-tree hash, key source hashes, firmware revision, resolved CODAL commit, and actual dynamic heap capacity. This is how the release proves which source produced the HEX.

Automated checks reduce risk but cannot prove the absence of every possible software defect or malicious behavior.

See `INSTRUCTIONS.md` for setup/troubleshooting, `INFO.md` for architecture, `README_WINDOWS.md` for Windows details, and `PROTOCOL.md` for the wire protocol.
