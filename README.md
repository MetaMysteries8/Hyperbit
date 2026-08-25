# HyperBit

[![Build, Scan & Release HyperBit](https://github.com/MetaMysteries8/Hyperbit/actions/workflows/build-firmware.yml/badge.svg)](https://github.com/MetaMysteries8/Hyperbit/actions/workflows/build-firmware.yml)

A physical voice AI agent with a **BBC micro:bit V2 + ELECFREAKS Wukong** as its wireless body and a **Windows PC** as its main home/brain.

The micro:bit handles push-to-talk, microphone capture, Bluetooth audio, its built-in speaker, the 5×5 display, and Wukong status lighting. The PC handles faster-whisper speech-to-text, the Charm Hyper tool-calling agent, memory/workspace, Windows SAPI TTS, and BLE transport.

## Download a ready build

The easiest path is the **Releases** page. A release is created automatically only after the configured build/security gates succeed.

Download `HyperBit-release.zip`. It contains:

- `HyperBit.hex` — compiled micro:bit V2 firmware.
- `HyperBit.py` — simple PC launcher.
- `pc_agent/` — supporting Python modules.
- `requirements.txt` and `config.example.cmd`.
- `HI.md`, `INSTRUCTIONS.md`, and `INFO.md`.
- flashing helpers.
- `SECURITY_SCAN.md`.

The release page also attaches SHA-256 checksums and raw security reports.

## Release gates

Before an automatic release is published, GitHub Actions must successfully complete:

- Python syntax/bytecode compilation.
- Bandit static analysis.
- pip-audit dependency vulnerability checking.
- ClamAV source scanning.
- GNU Arm/CODAL firmware compilation.
- ClamAV scanning of the final firmware and ZIP.
- SHA-256 checksum generation.

These checks reduce risk but cannot prove the absence of every possible defect or malicious behavior.

## Flashing

Plug the **micro:bit itself** into your PC over USB and copy `HyperBit.hex` to the `MICROBIT` drive. The Wukong is an expansion board and is not separately flashed.

After flashing, unplug USB and use the Wukong battery.

## Windows setup

From the release ZIP:

```bat
py -3 -m pip install -r requirements.txt
set HYPER_API_KEY=sk-hyper-your-key
py -3 HyperBit.py
```

The scanned release currently uses **Windows SAPI** for offline TTS.

## Physical controls

- **Hold gold logo:** record speech.
- **Release logo:** upload compressed audio over BLE.
- **Built-in microphone:** voice input.
- **Built-in speaker:** short TTS response.
- **Wukong battery:** wireless power.
- **Wukong blue base LEDs:** connection/agent state.

Wukong state lighting:

- breathing — PC disconnected
- dim — connected / idle
- medium — listening
- brighter — transcribing
- bright — thinking
- full — speaking / error

## Architecture

```text
micro:bit V2 + Wukong
  gold logo + microphone
          |
      IMA ADPCM
          |
          BLE
          |
Windows PC
  faster-whisper
  Charm Hyper + tools
  memory/workspace
  Windows SAPI
          |
      IMA ADPCM
          |
          BLE
          |
micro:bit V2 speaker
```

See `PROTOCOL.md` for the BLE protocol and `README_WINDOWS.md` for more setup/build details.
