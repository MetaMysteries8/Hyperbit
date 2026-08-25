# HyperBit Info

HyperBit is a PC-hosted voice AI agent with a **BBC micro:bit V2 + ELECFREAKS Wukong** as its physical wireless body.

## micro:bit V2

- Gold capacitive logo = push-to-talk.
- Built-in microphone = speech capture.
- Built-in speaker = spoken responses.
- A = interrupt/cancel.
- B = replay.
- A+B = mute toggle.
- BLE = bidirectional compressed audio/control.

The microphone hardware is only activated while the gold logo is held.

## Wukong

Wukong is actively driven by the firmware rather than merely serving as a battery holder:

- built-in battery powers the handheld agent,
- eight blue base LEDs are controlled by Wukong's I2C controller,
- four Rainbow LEDs on P16 are used for visible agent-state colors,
- boot performs a visible Wukong self-test.

## Windows PC

The PC is the agent's main home:

- faster-whisper for local speech-to-text,
- Charm Hyper for the model/tool loop,
- durable memory and sandboxed workspace,
- Windows SAPI for local TTS,
- Bleak for Bluetooth.

The Hyper API key remains on the PC.

## Audio transport

Audio is 8 kHz mono IMA ADPCM.

Input is streamed in BLE-sized chunks while push-to-talk is held, avoiding a giant microphone recording in RAM.

Output is segmented into <=4096-byte ADPCM pieces, then each piece is packetized over BLE and acknowledged before the next piece is sent.

## Release verification

Automatic releases are only published after the configured Python syntax checks, Bandit analysis, dependency vulnerability audit, ClamAV scans, and successful micro:bit V2 firmware compilation complete.

Automated scanning improves release hygiene but cannot mathematically prove that software contains no possible bug or malicious behavior.
