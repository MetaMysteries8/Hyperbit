# HyperBit Instructions

## 1. Flash the firmware

Plug the **micro:bit V2 itself** into the Windows PC over USB.

The release ZIP already contains `HyperBit.hex` at its root. Double-click:

```text
FLASH_FIRMWARE.bat
```

The Wukong is not flashed separately. The firmware runs on the micro:bit and directly controls Wukong hardware.

At boot, the Wukong should visibly self-test:
- its eight blue base LEDs change state,
- its four Rainbow LEDs on P16 flash red, green, blue, then white.

If those do not happen, tell us; that specifically means the Wukong driver needs attention.

## 2. Configure the PC agent

The easiest launcher is:

```text
RUN_HYPERBIT.bat
```

On the first run it creates `config.cmd` from `config.example.cmd` if needed. Put your Hyper API key in `config.cmd` and run the launcher again.

The launcher also avoids the common Windows problem where `py -3`, `python`, and `python3` point at different Python installations.

## 3. Physical controls

- **Hold the V2 gold logo at the top:** microphone hardware turns ON and speech is sent in small BLE packets.
- **Release the gold logo:** microphone hardware turns OFF and the utterance ends.
- **A:** cancel the current response; while speaking, interrupt playback.
- **B:** replay the last spoken answer.
- **A+B:** mute/unmute speaker output.

The microphone is deliberately deactivated whenever the gold logo is not being held.

## 4. Wukong behavior

HyperBit uses both:
- Wukong's eight programmable blue base LEDs through its I2C controller.
- Wukong's four Rainbow/NeoPixel LEDs on P16.

The LEDs show connection and agent state such as idle, listening, uploading, thinking, speaking, muted, and error.

## 5. BLE connection behavior

HyperBit now uses the conventional **Nordic UART Service (NUS)** UUID layout instead of the older HyperBit-specific three-characteristic service.

While Windows is establishing the raw BLE/NUS session, the firmware deliberately disables the micro:bit 5x5 display refresh driver and pauses animation, accelerometer reads, Wukong updates, microphone work, and speaker PWM. A briefly blank 5x5 during connection is therefore intentional; the face comes back after the HyperBit HELLO/READY handshake completes or the connection drops.

## 6. Audio size / chunking

HyperBit does not try to shove a large audio file into the micro:bit.

Microphone audio is streamed as tiny BLE packets while the logo is held.

TTS is split by the PC into segments of at most **512 ADPCM bytes**. Each segment is then split into <=20-byte NUS frames. The PC waits for the micro:bit to finish one segment before sending the next.

## Troubleshooting BLE

If the agent says no HyperBit was found, the launcher prints every BLE device Windows saw, including names, addresses, and advertised service UUIDs. Copy that block back for diagnosis.

Every scanned release also includes `BUILD_PROVENANCE.txt`, which records the exact source-tree hash, CODAL commit, BLE config verification, and calculated CODAL heap capacity used to produce that HEX.
