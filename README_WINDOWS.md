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

The micro:bit V2 application MCU is Nordic's **nRF52833**, a 64 MHz Cortex-M4F with 512 KiB flash and 128 KiB RAM. Those resources are shared by CODAL, SoftDevice reservations, heap/stack, buffers, and the application.

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

The current hardened firmware is protocol **v2**, revision **r5**. The PC requires buffered-HVN and bounded-link-recovery capabilities, so an older HEX is rejected explicitly.

While raw GATT setup is in progress, r5 **freezes the last rendered 5×5 frame without disabling CODAL's LED-matrix hardware**. It schedules no new fluid animation, accelerometer reads, Wukong writes, microphone work, speaker work, or button handling until READY succeeds. Keeping the TIMER4 display lifecycle stable removes the previous disable/re-enable recovery failure surface.

If Windows leaves a raw connection half-open, firmware allows roughly 38 seconds for the 35-second GATT setup window, requests a normal GAP disconnect, then gives the SoftDevice about two seconds to report the link gone. If it still claims to be connected, the MCU/SoftDevice resets so the board cannot remain trapped indefinitely.

After that recovery window, the PC performs a fresh BLE scan and reacquires the board before creating the next `BleakClient`, instead of repeatedly using the WinRT `BLEDevice` object associated with the failed GATT session.

If an already-valid voice session later disconnects, the PC agent automatically scans and reconnects. Delayed callbacks from superseded Bleak clients are ignored so they cannot kill a newer healthy session.

## Animation/resource behavior

Routine matrix animation is 25 Hz in r5 rather than roughly 33 Hz. The five-particle fluid renderer uses fixed-point integer state, and accelerometer data is sampled only for disconnected/idle fluid states. Listening, uploading, transcription, thinking, speaking, error, and muted shapes do not perform gravity reads they cannot use.

The size of `HyperBit.hex` in Explorer is not the linked application flash usage. Intel HEX is an ASCII container and the release image includes non-application regions. Use `BUILD_PROVENANCE.txt` from the release for actual linked application flash/static-RAM/heap measurements.

## Audio transport

Audio is 8 kHz mono IMA ADPCM.

- Microphone: streamed while the gold logo is held through a 512-byte ring buffer and <=20-byte BLE frames.
- Firmware: a reviewed build-time CODAL override configures a 12-entry SoftDevice GATTS notification queue before BLE is enabled.
- TTS: continuous ADPCM stream split into acknowledged <=512-byte segments, then <=20-byte BLE frames.
- The PC checks mic sequence numbers and warns if a packet gap/overflow makes an utterance incomplete.

At 4 bits per 8 kHz sample, the microphone produces about 4,000 ADPCM bytes/s. With 17 audio bytes per protocol-v2 notification that is roughly 236 notifications/s, which is why the one-entry Nordic default queue was replaced instead of relying on retry timing alone.

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

## Building firmware locally

`BUILD_FIRMWARE.bat` mirrors the release build instead of simply reusing whatever CODAL tree happens to exist. It resets the sample checkout, removes generated build/dependency trees, CMake-configures the locked CODAL revision, applies `firmware/apply_codal_overrides.py`, then compiles.

The override pins the reviewed CODAL commit and moves both the application RAM boundary and the 16-byte NOINIT region out of the expanded SoftDevice reservation. It refuses to patch an unexpected upstream revision or source anchor.

## Release verification

The automatic release pipeline must pass syntax checking, protocol/BLE/transport regression tests, Bandit static analysis, pip-audit, ClamAV source/package scans, exact source injection, locked-CODAL verification, a verified 12-entry GATTS notification queue, reserved RAM/NOINIT boundary checks, open-link BLE security verification, a guard against IRQ-masking Rainbow code, CODAL/GNU Arm compilation, final-ELF application-boundary verification, and a minimum 64 KiB calculated heap capacity.

Each release includes `BUILD_PROVENANCE.txt`, checksums, test output, and security reports. The provenance records the exact queue/RAM configuration and patched CODAL hashes in addition to source and firmware identity.

Automated gates reduce risk but cannot prove the absence of every possible defect; the release still needs real-device BLE/audio testing.

See `INSTRUCTIONS.md` for the recommended test order and `PROTOCOL.md` for the wire protocol.
