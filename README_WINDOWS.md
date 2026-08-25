# HyperBit — Windows PC package

HyperBit is a PC-hosted AI agent with a BBC micro:bit V2 + ELECFREAKS Wukong physical body.

## What runs where

### micro:bit V2 + Wukong
- gold logo = hold-to-talk
- built-in mic = voice input
- built-in speaker = voice output
- BLE = compressed voice transport
- 5x5 display = status
- Wukong battery = wireless power
- Wukong 8 blue base LEDs = agent state

### Windows PC
- faster-whisper = local speech-to-text
- Charm Hyper = model + tool calls
- Windows SAPI or gTTS = text-to-speech
- agent_home = durable memory + workspace
- Bleak = Bluetooth link

The Hyper API key stays on the PC.

---

# Fast setup

## 1. Run SETUP_PC.bat

It creates `.venv` and installs the Python dependencies.

It also creates `config.cmd` from `config.example.cmd`.

## 2. Edit config.cmd

Set:

    set "HYPER_API_KEY=sk-hyper-your-key"

TTS:

    set "HYPERBIT_TTS=sapi"

or:

    set "HYPERBIT_TTS=gtts"

SAPI is offline and simplest. gTTS uses the internet. gTTS MP3 is decoded with miniaudio, so no ffmpeg install is needed.

## 3. Test the PC brain

Run:

    TEST_BRAIN.bat

Do this before worrying about Bluetooth.

## 4. Build the real micro:bit V2 .hex

Run:

    BUILD_FIRMWARE.bat

This uses WinGet to install missing build prerequisites:
- Git
- CMake
- Ninja
- Arm GNU Embedded Toolchain

Then it clones Lancaster University's official `microbit-v2-samples`, copies HyperBit's Wukong/BLE/audio firmware into it, runs `python build.py`, and places the real output here:

    firmware\HyperBit.hex

The first build downloads CODAL dependencies and can take a while.

## 5. Flash

Plug the micro:bit itself into USB.

Run:

    FLASH_FIRMWARE.bat

The Wukong is an expansion board; it is NOT separately flashed. HyperBit.hex runs on the micro:bit and contains the Wukong driver.

After flashing, you can disconnect USB and use the Wukong battery.

## 6. Run the physical agent

Run:

    RUN_AGENT.bat

Expected basic flow:

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
        Whisper transcription
        Hyper tool/model call
        SAPI or gTTS

    micro:bit shows S
        short answer plays from built-in speaker

---

# Wukong support

This is not merely using Wukong as a battery holder.

The firmware directly controls Wukong's 8 programmable blue base LEDs through its I2C controller.

Current state mapping:
- breathing = disconnected
- dim = connected / idle
- medium = listening
- brighter = transcribing
- bright = thinking
- full = speaking / error

The four P16 Rainbow LEDs are intentionally not driven in this first build. NeoPixel timing plus BLE audio makes debugging harder; they are a good v2 feature after the core voice round-trip is stable.

The micro:bit's own speaker is used for voice output. Audio output to edge pin P0 is disabled so the Wukong buzzer does not try to reproduce speech.

---

# Firmware transport

8 kHz, mono IMA ADPCM.

The device records while the gold logo is held, then transfers after release. This first build is store-and-forward instead of real-time streaming because it is much more tolerant of Windows BLE timing.

See `PROTOCOL.md`.

---

# Important current limits

- about 4 seconds maximum recorded utterance in the initial firmware buffer
- about 5 seconds maximum spoken answer
- short agent responses are intentionally preferred
- the first Whisper run downloads the configured model
- custom firmware requires micro:bit V2

---

# If BUILD_FIRMWARE.bat fails

The official CODAL project requires GNU Arm Embedded, Git, CMake, Python 3, and Ninja on Windows.

The script installs these with WinGet when possible. If a newly installed command is not visible to the current shell, close the window and run BUILD_FIRMWARE.bat again.

The official resulting file from CODAL is `MICROBIT.hex`; the build script copies it to `firmware\HyperBit.hex`.
