# HyperBit

[![Build, Scan & Release HyperBit](https://github.com/MetaMysteries8/Hyperbit/actions/workflows/build-firmware.yml/badge.svg)](https://github.com/MetaMysteries8/Hyperbit/actions/workflows/build-firmware.yml)

A physical voice AI agent with a **BBC micro:bit V2 + ELECFREAKS Wukong** as its wireless body and a **Windows PC** as its main home/brain.

## Download

Use the latest GitHub Release and download `HyperBit-release.zip`. The release is created automatically only after firmware compilation and the configured security/provenance gates pass.

The release includes the compiled `HyperBit.hex`, the Windows agent, `RUN_HYPERBIT.bat`, flashing helpers, configuration template, instructions, protocol documentation, checksums, security information, and `BUILD_PROVENANCE.txt` showing exactly what produced the HEX.

## What the physical device does

The **V2 gold capacitive logo at the top** is the only push-to-talk control. The microphone hardware is deactivated at rest, activated when the logo is held, and deactivated again when the logo is released.

Controls:

- **Hold gold logo:** microphone ON; stream compressed speech to the PC.
- **Release gold logo:** microphone OFF; finish the utterance.
- **A:** cancel/interrupt the current response.
- **B:** replay the last spoken answer.
- **A+B:** mute/unmute speaker output.

Audio is transported as 8 kHz mono IMA ADPCM. Mic audio is streamed through a small ring buffer instead of storing one huge recording. TTS is split into acknowledged <=512-byte segments, then further packetized into <=20-byte BLE frames.

## Wukong is part of the device

The firmware actively uses the Wukong rather than treating it only as a battery holder:

- Wukong battery provides wireless power.
- Eight blue base LEDs are controlled through Wukong's I2C light controller.
- Four Rainbow LEDs on **P16** display visible agent states.
- Boot runs a Wukong self-test: base-light changes plus red -> green -> blue -> white on the Rainbow LEDs.

States include disconnected, idle, listening, uploading, transcribing, thinking, speaking, muted, and error.

## BLE transport

HyperBit uses the standard **Nordic UART Service (NUS)** UUID layout: one RX write characteristic and one TX notify characteristic. HyperBit control, microphone, and TTS frames are multiplexed over those two channels with an explicit protocol-v2 HELLO/READY handshake.

BLE still uses GATT underneath because that is the application-data transport provided by the micro:bit SoftDevice and Windows BLE stack, but HyperBit no longer uses its older bespoke three-characteristic GATT layout.

While the raw Bluetooth/NUS connection is being established, firmware disables the 5x5 display refresh driver and performs no fluid animation, accelerometer reads, Wukong updates, microphone work, or speaker PWM work. Connection setup gets priority; the face resumes after the application handshake succeeds or the link drops.

## Windows setup

Extract the release ZIP, copy `config.example.cmd` to `config.cmd` if needed, put your Hyper API key in it, then use:

```text
RUN_HYPERBIT.bat
```

The launcher deals with Windows machines where `py -3`, `python`, and `python3` point to different Python installations, and installs the requirements if necessary.

To flash the included firmware, plug the **micro:bit itself** into USB and run:

```text
FLASH_FIRMWARE.bat
```

The Wukong is not separately flashed. `HyperBit.hex` runs on the micro:bit and contains the Wukong drivers.

## PC side

The Windows PC handles:

- faster-whisper local speech-to-text,
- Charm Hyper model/tool calls,
- durable agent memory and sandboxed workspace,
- Windows SAPI TTS,
- BLE transport using Bleak.

The Hyper API key stays on the PC.

## Release gates

Before an automatic release is published, GitHub Actions must successfully complete Python syntax checking, Bandit static analysis, pip-audit dependency vulnerability checking, ClamAV source scanning, GNU Arm/CODAL firmware compilation, full firmware source-tree injection verification, BLE security-config verification, real CODAL heap-capacity extraction from the ELF, ClamAV scanning of the final HEX/ZIP, and SHA-256 checksum generation.

CODAL's generic linker `RAM % used` includes its fill-to-limit `.heap` section and is therefore not treated as free-heap information; `BUILD_PROVENANCE.txt` records a separate heap-capacity calculation from the linked ELF.

Automated checks reduce risk but cannot prove the absence of every possible software defect or malicious behavior.

See `INSTRUCTIONS.md` for use, `INFO.md` for architecture, and `PROTOCOL.md` for the BLE protocol.
