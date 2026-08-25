# HyperBit — Windows PC

HyperBit is designed to run its AI/STT/TTS side on a **Windows PC**. The BBC micro:bit V2 + ELECFREAKS Wukong is the wireless physical terminal.

## Recommended setup: use a GitHub Release

You normally do **not** need to compile the firmware yourself.

1. Open the repository's **Releases** page.
2. Download the latest `HyperBit-release.zip`.
3. Extract the whole ZIP.
4. Plug the micro:bit V2 itself into USB.
5. Copy `HyperBit.hex` onto the `MICROBIT` drive, or run `FLASH_FIRMWARE.bat`.
6. Install the PC dependencies:

       py -3 -m pip install -r requirements.txt

7. Set your Hyper API key:

       set HYPER_API_KEY=sk-hyper-your-key

8. Start the agent:

       py -3 HyperBit.py

The first faster-whisper run may download its model.

## TTS

The scanned default release uses **Windows SAPI**. It is offline and already part of Windows, which avoids another network TTS dependency.

## What runs where

### micro:bit V2 + Wukong

- gold logo = hold-to-talk
- built-in mic = voice input
- built-in speaker = voice output
- BLE = compressed voice transport
- 5×5 display = status
- Wukong battery = wireless power
- Wukong 8 blue base LEDs = agent state

### Windows PC

- faster-whisper = local speech-to-text
- Charm Hyper = model + tool calls
- Windows SAPI = text-to-speech
- agent home = durable memory + workspace
- Bleak = Bluetooth link

The Hyper API key stays on the PC.

## Expected physical flow

```text
Wukong LEDs breathing
    PC not connected

PC connects
    micro:bit shows I
    LEDs dim steady

hold gold logo
    micro:bit shows L
    speak

release logo
    micro:bit shows U
    compressed mic audio uploads over BLE

PC
    faster-whisper transcription
    Hyper agent/tool call
    Windows SAPI TTS

micro:bit shows S
    short answer plays from built-in speaker
```

## Wukong support

The firmware directly controls Wukong's eight programmable blue base LEDs over I2C; the board is not just being used as a battery holder.

Current states:

- breathing = disconnected
- dim = connected / idle
- medium = listening
- brighter = transcribing
- bright = thinking
- full = speaking / error

The four P16 Rainbow LEDs are intentionally unused in the first hardware build so NeoPixel timing does not complicate BLE audio debugging.

The micro:bit's own speaker is used for voice output. Audio output to edge pin P0 is disabled so the Wukong buzzer does not try to reproduce speech.

## Firmware transport

Audio is 8 kHz mono IMA ADPCM. The device records while the gold logo is held, then transfers after release. This first build is store-and-forward rather than live streaming because it is much more tolerant of Windows BLE timing.

## Current limits

- about 4 seconds maximum recorded utterance in the initial firmware buffer
- about 5 seconds maximum spoken answer
- short agent responses are preferred
- custom firmware requires a micro:bit V2

## Automatic release verification

GitHub Actions refuses to publish a release unless the configured Python syntax checks, Bandit scan, pip-audit dependency check, ClamAV source/package scans, and CODAL firmware compilation succeed. Release assets include SHA-256 checksums and raw scan reports.

No automated scanner can guarantee that arbitrary software is free of every possible vulnerability or malicious behavior, but a failed configured gate prevents publication.

## Building locally anyway

If you want to build from source, `BUILD_FIRMWARE.bat` / `BUILD_FIRMWARE.ps1` can install/use the GNU Arm toolchain and Lancaster University's official `microbit-v2-samples` CODAL project. GitHub Actions is the easier route.
