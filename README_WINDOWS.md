# HyperBit — Windows PC

HyperBit runs its AI/STT/TTS side on a **Windows PC**. A **BBC micro:bit V2 + ELECFREAKS Wukong** is the wireless physical terminal.

## Recommended setup

Use the latest GitHub Release and keep its PC files and firmware together:

1. Download and extract `HyperBit-release.zip`.
2. Plug the micro:bit V2 itself into USB.
3. Run `FLASH_FIRMWARE.bat`.
4. Run `TEST_BLE.bat` before configuring the AI.
5. After BLE passes, run `RUN_HYPERBIT.bat`, put your Hyper key in the generated private `config.cmd`, save it, and run the launcher again.

`TEST_BLE.bat` does not require a Hyper API key. It validates Windows discovery, NUS, notification subscription, HELLO/READY, firmware revision/capabilities, and a short stability window.

## What runs where

### micro:bit V2 + Wukong

- gold logo = hold-to-talk
- built-in microphone = 8 kHz voice input
- built-in speaker = voice output
- A = cancel/interrupt
- B = replay
- A+B = mute toggle
- 5×5 matrix = animated local status outside connection setup
- Wukong 8 blue base LEDs = dynamic body/status glow
- Wukong 4 Rainbow LEDs = state colors via CODAL hardware PWM
- Wukong battery = wireless power

### Windows PC

- Bleak = BLE/NUS transport
- faster-whisper = local speech-to-text
- Charm Hyper = model + tool calls
- Windows SAPI = offline text-to-speech
- agent home = durable memory + sandboxed workspace

The Hyper API key stays on the PC.

## BLE connection behavior

HyperBit uses the conventional Nordic UART Service UUID layout with a small framed audio/control protocol on top. BLE still uses GATT underneath because that is the application transport exposed by Windows and the micro:bit SoftDevice.

A connection becomes usable only after:

```text
Windows raw BLE link
    -> NUS discovery
    -> TX notifications enabled
    -> PC HELLO
    -> firmware READY(protocol, revision, capabilities)
    -> PC validates firmware
```

The current hardened firmware is protocol **v2**, revision **r3**.

While that handshake is in progress, the micro:bit 5×5 display is deliberately **black**: firmware disables the matrix refresh driver and performs no fluid animation, accelerometer reads, Wukong updates, microphone work, speaker work, or button handling. Normal visuals resume only after READY has successfully been queued.

If Windows leaves a half-open raw connection, firmware evicts it after about 45 seconds. If an already-valid voice session later disconnects, the PC agent automatically scans and reconnects.

## Audio transport

Audio is 8 kHz mono IMA ADPCM.

- Microphone: streamed while the gold logo is held through a 512-byte ring buffer and <=20-byte BLE frames.
- TTS: continuous ADPCM stream split into acknowledged <=512-byte segments, then <=20-byte BLE frames.
- The PC checks mic sequence numbers and warns if a packet gap/overflow makes an utterance incomplete.

There is no old fixed four-second whole-utterance firmware buffer anymore.

## Rainbow LEDs and BLE

Older HyperBit experiments used a custom WS2812 timing routine that masked interrupts; live Rainbow updates were then disabled once BLE started. That is no longer the design.

micro:bit V2 CODAL enables its hardware NeoPixel implementation, which uses NRF PWM2. HyperBit uses that path for P16 Rainbow LEDs, while built-in speaker audio uses NRF PWM1. This lets the state colors remain live without intentionally starving the BLE SoftDevice.

## Python launcher

`RUN_HYPERBIT.bat` tries `python3`, `py -3`, and `python`, checks the actual required modules (including `faster_whisper` for normal voice mode), and installs `requirements.txt` if necessary.

Manual equivalent:

```text
py -3 -m pip install -r requirements.txt
copy config.example.cmd config.cmd
notepad config.cmd
call config.cmd
py -3 HyperBit.py
```

BLE-only manual test:

```text
py -3 HyperBit.py --ble-test
```

## Release verification

The automatic release pipeline must pass syntax checking, protocol/BLE regression tests, Bandit static analysis, pip-audit, ClamAV source/package scans, CODAL/GNU Arm compilation, full firmware source-tree provenance comparison, open-link BLE security verification, a guard against IRQ-masking Rainbow code, and linked-ELF heap-capacity extraction.

Each release includes `BUILD_PROVENANCE.txt`, checksums, test output, and security reports. Automated gates reduce risk but cannot prove the absence of every possible defect.

See `INSTRUCTIONS.md` for the recommended test order and `PROTOCOL.md` for the wire protocol.
