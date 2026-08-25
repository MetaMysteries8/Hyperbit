# HyperBit Instructions

## 1. Use one release as a matched pair

Download the latest `HyperBit-release.zip` and extract the **whole** ZIP. Use the `HyperBit.hex` and PC files from that same release together.

The PC agent validates the firmware revision and capabilities during HELLO/READY, so accidentally mixing a new PC agent with an old flashed HEX produces an explicit stale-firmware error instead of a mysterious connection failure.

## 2. Flash the firmware

Plug the **micro:bit V2 itself** into the Windows PC over USB, then double-click:

```text
FLASH_FIRMWARE.bat
```

The Wukong is not flashed separately. The firmware runs on the micro:bit and directly controls Wukong hardware.

At boot, Wukong should visibly self-test:

- its eight blue base LEDs change state,
- its four Rainbow LEDs on P16 flash red, green, blue, then white.

If that self-test does not happen, diagnose Wukong/power before the AI stack.

## 3. Test Bluetooth before configuring the AI

Double-click:

```text
TEST_BLE.bat
```

This mode requires **no Hyper API key**. It tests only:

- Windows BLE discovery,
- Nordic UART Service discovery,
- TX notification subscription,
- HyperBit HELLO/READY,
- protocol + firmware revision + capability validation,
- a two-second post-handshake stability window.

A current board should report **protocol v2, firmware revision r4 or newer, and the buffered-HVN capability**.

During the raw connection/handshake window the 5×5 display intentionally goes **black**. Firmware disables the matrix refresh driver and does no animation, accelerometer, Wukong, microphone, speaker, or button work until READY has been successfully queued. That is deliberate connection isolation, not a frozen fluid renderer.

If `TEST_BLE.bat` fails, copy the `[ble]` output. You can also target one board explicitly:

```text
RUN_HYPERBIT.bat --ble-test --address E7:3F:04:AA:4A:AC
```

or by a name substring:

```text
RUN_HYPERBIT.bat --ble-test --name "BBC micro:bit"
```

## 4. Configure the PC agent

The easiest launcher is:

```text
RUN_HYPERBIT.bat
```

On the first normal run it creates `config.cmd` from `config.example.cmd` if needed. Put your Hyper API key in `config.cmd`, save it, then run the launcher again.

Keep `config.cmd` private; it is intentionally excluded from the repository and release assets.

The launcher checks for the required Python modules, including faster-whisper, and installs `requirements.txt` if needed. The first faster-whisper use may download the configured model.

## 5. Physical controls

- **Hold the V2 gold logo at the top:** microphone hardware turns ON and compressed speech streams to the PC.
- **Release the gold logo:** microphone hardware turns OFF and the utterance ends.
- **A:** cancel the current response; while speaking, interrupt playback.
- **B:** replay the last spoken answer.
- **A+B:** mute/unmute speaker output.

The microphone is deliberately deactivated whenever the gold logo is not being held.

## 6. Physical state display

HyperBit uses both parts of Wukong's lighting hardware:

- eight blue base LEDs over Wukong's I2C controller,
- four Rainbow/NeoPixel LEDs on P16 using CODAL's hardware-PWM path.

The 5×5 matrix and Wukong lights show disconnected, idle, listening, uploading, transcribing, thinking, speaking, muted, and error states. Rainbow state updates do not use the old interrupt-masking bit-banger.

## 7. Audio transport

HyperBit does not store a whole conversation-sized audio file on the micro:bit.

Microphone audio is 8 kHz mono IMA ADPCM streamed as tiny BLE packets while the logo is held through a 512-byte ring buffer. Firmware r4 also configures a 12-entry Nordic SoftDevice notification queue so brief Windows connection-event scheduling gaps do not immediately force the application into one-packet-at-a-time backpressure.

TTS is split by the PC into at most 512 ADPCM bytes per acknowledged segment, with each segment further divided into <=20-byte NUS frames.

If the microphone transport still cannot keep up, the firmware/PC marks the utterance as overflowed or packet-gapped instead of silently treating damaged ADPCM as clean audio.

## 8. Disconnect recovery

After a valid voice session has connected, an unexpected Bluetooth disconnect no longer leaves the agent stuck waiting forever. The PC agent notices the session loss, closes the stale client, scans again, and keeps retrying until the board returns or you press Ctrl+C.

Firmware also evicts a raw half-open Windows connection after about 45 seconds so the board can advertise again.

## 9. Building locally

Normal users should use the compiled release HEX. If you intentionally build from source, `BUILD_FIRMWARE.bat` now reproduces the release build order:

1. reset the official `microbit-v2-samples` checkout,
2. remove stale generated `build/` and `libraries/` trees,
3. inject this checkout's firmware,
4. CMake-configure the locked CODAL dependencies,
5. run `firmware/apply_codal_overrides.py`, which verifies the expected CODAL commit and applies the reviewed notification-queue/RAM layout,
6. compile the HEX.

The override is fail-closed: an unexpected CODAL revision/source layout must be reviewed rather than patched blindly.

## Troubleshooting order

Use this order so failures stay isolated:

1. Confirm Wukong boot self-test.
2. Flash the `HyperBit.hex` from the same release ZIP as the PC agent.
3. Run `TEST_BLE.bat` until protocol v2 / firmware r4 validation is stable.
4. Only then configure the Hyper API key and run full voice mode.
5. If full mode fails after BLE passes, the problem is above the transport layer (dependencies, Whisper, Hyper API, or TTS) rather than firmware discovery.
