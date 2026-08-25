# HyperBit Info

HyperBit is a PC-hosted voice AI agent with a **BBC micro:bit V2 + ELECFREAKS Wukong** as its physical wireless body.

## What the micro:bit/Wukong does

- Gold logo push-to-talk control.
- Built-in microphone capture.
- Bluetooth Low Energy audio transport.
- Built-in speaker playback.
- 5×5 status display.
- Wukong battery power.
- Wukong programmable blue base LEDs for agent state.

## What the Windows PC does

- Local speech-to-text with faster-whisper.
- Charm Hyper chat-completions/tool-calling agent.
- Durable memory and a sandboxed workspace.
- TTS using Windows SAPI or optional gTTS.
- Bluetooth communication using Bleak.

## Audio transport

Voice is transported as 8 kHz mono IMA ADPCM. The current firmware records while the gold logo is held, then transfers the compressed utterance after release.

## Release verification

The Hyper API key exists only on the PC. It is never sent to or stored on the micro:bit.

Automatic releases are published only after the configured source checks, dependency audit, antivirus scan, and firmware compile finish successfully. Each release also includes a generated scan report and SHA-256 checksums.
