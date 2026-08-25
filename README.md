# HyperBit

[![Build HyperBit](https://github.com/MetaMysteries8/Hyperbit/actions/workflows/build-firmware.yml/badge.svg)](https://github.com/MetaMysteries8/Hyperbit/actions/workflows/build-firmware.yml)

A physical voice AI agent with a **BBC micro:bit V2 + ELECFREAKS Wukong** as its wireless body and a **Windows PC** as its main home/brain.

The micro:bit handles push-to-talk, microphone capture, Bluetooth audio, its built-in speaker, the 5×5 display, and Wukong status lighting. The Windows PC handles local speech-to-text, the Charm Hyper agent/tool loop, memory/workspace, TTS, and BLE transport.

## Easiest way to get the compiled firmware

You do **not** need to install a C++ compiler.

1. Open the **Actions** tab.
2. Open **Build HyperBit**.
3. Use the newest successful run, or click **Run workflow** to build it manually.
4. Download the **HyperBit-build** artifact.
5. Inside it:
   - `HyperBit.hex` — flash this directly to the micro:bit V2.
   - `HyperBit-Windows-PC.zip` — the complete Windows project with that compiled HEX already inside it.

GitHub Actions compiles the firmware using Lancaster University's official `microbit-v2-samples` CODAL build system and the GNU Arm Embedded toolchain.

## Flashing

Plug the **micro:bit itself** into the PC over USB. The Wukong is an expansion board and is not separately flashed.

Either drag `HyperBit.hex` onto the `MICROBIT` drive or, from the full Windows package, run:

```text
FLASH_FIRMWARE.bat
```

After flashing, disconnect USB and power the micro:bit from the Wukong battery.

## Windows agent setup

From `HyperBit-Windows-PC.zip`:

1. Run `SETUP_PC.bat`.
2. Edit `config.cmd` and set your Hyper API key.
3. Run `TEST_BRAIN.bat`.
4. Run `RUN_AGENT.bat`.

Example config:

```bat
set "HYPER_API_KEY=sk-hyper-REPLACE_ME"
set "HYPER_MODEL=deepseek-v4-flash"
set "HYPERBIT_TTS=sapi"
```

TTS choices currently included:

- `sapi` — offline Windows speech synthesis.
- `gtts` — Google TTS; internet required.

## Physical controls

- **Hold gold logo:** record speech.
- **Release logo:** upload compressed audio over BLE.
- **Built-in microphone:** voice input.
- **Built-in speaker:** short TTS response.
- **Wukong battery:** wireless power.
- **Wukong blue base LEDs:** connection/agent state.

Current Wukong states:

- breathing — PC disconnected
- dim — connected / idle
- medium — listening
- brighter — transcribing
- bright — thinking
- full — speaking / error

The four P16 Rainbow LEDs are intentionally left unused in the first hardware build so NeoPixel timing does not complicate BLE audio debugging.

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
  SAPI or gTTS
          |
      IMA ADPCM
          |
          BLE
          |
micro:bit V2 speaker
```

See [`PROTOCOL.md`](PROTOCOL.md) for the BLE protocol and [`README_WINDOWS.md`](README_WINDOWS.md) for the longer Windows setup notes.

## Firmware build details

The Action checks out this repository, installs the Arm toolchain, clones `lancaster-university/microbit-v2-samples`, replaces its sample source with `firmware/source/`, and runs:

```bash
python3 build.py
```

The resulting `MICROBIT.hex` becomes `HyperBit.hex` in the downloadable artifact.
