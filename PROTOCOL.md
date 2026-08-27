# HyperBit BLE protocol

HyperBit uses the standard Nordic UART Service (NUS) UUID layout instead of the old custom three-characteristic service.

| NUS item | UUID | Direction |
|---|---|---|
| Service | `6e400001-b5a3-f393-e0a9-e50e24dcca9e` | — |
| RX | `6e400002-b5a3-f393-e0a9-e50e24dcca9e` | PC -> micro:bit write |
| TX | `6e400003-b5a3-f393-e0a9-e50e24dcca9e` | micro:bit -> PC notify |

BLE still uses GATT underneath because that is the application-data transport exposed by the micro:bit/Windows BLE stack. HyperBit no longer invents its own service layout: all application packets are multiplexed over the conventional two-characteristic NUS shape.

The current firmware additionally delegates NUS UUID, primary-service, characteristic, and handle registration to CODAL v0.3.4's own `MicroBitUARTService`. The locked build patch changes only CODAL UART TX from indication to standard NUS notification semantics so the existing streamed-audio transport keeps its required throughput.

Audio is 8 kHz mono IMA ADPCM. Every new microphone utterance starts with predictor=0/index=0. TTS is one continuous ADPCM stream split into acknowledged 512-byte segments; the decoder resets only on the first segment.

## Versioning

The current wire protocol is **v2** and the hardened firmware revision is **r5**.

Protocol version and firmware revision are separate on purpose: compatible protocol-v2 firmware can gain runtime fixes without gratuitously changing every packet definition. The PC requires firmware revision 5 or newer so an accidentally flashed old HEX is diagnosed immediately.

Current capability bits reported by firmware:

- `0x01` — connection-isolated handshake: application peripherals stay suspended until READY is queued.
- `0x02` — Wukong Rainbow LEDs use the BLE-safe hardware-PWM NeoPixel path.
- `0x04` — acknowledged segmented TTS transport.
- `0x08` — buffered SoftDevice server-notification transport for streamed microphone audio.
- `0x10` — bounded recovery for a half-open raw BLE/GATT link, including MCU/SoftDevice reset fallback.
- `0x20` — NUS GATT registration is owned by locked CODAL `MicroBitUARTService` rather than HyperBit-authored service creation.

A current CODAL-UART-backed r5 build therefore reports capability mask **`0x3F`**. Older compatible r5 builds before this GATT-registration change report `0x1F`.

## Session handshake

1. Windows establishes the raw BLE link and discovers NUS.
2. The PC enables notifications on NUS TX.
3. The PC writes HELLO to NUS RX:

   `A3 02`

   - `A3` = HELLO frame.
   - `02` = HyperBit protocol version 2.

4. Firmware accepts HELLO **only if TX notifications are already enabled**.
5. Firmware attempts to queue READY. On the CODAL-UART-backed r5 implementation it is:

   `A0 12 02 05 3F`

   - `12` = READY event.
   - `02` = protocol v2.
   - `05` = firmware revision r5.
   - `3F` = capability bitmask.

6. Only after READY is successfully queued does firmware resume normal application animation and accelerometer, Wukong, microphone/button, and agent work.
7. The PC validates protocol, minimum firmware revision, and required capability bits before accepting the device as HyperBit.

A raw Bluetooth connection therefore does **not** mean HyperBit is ready. A generic NUS device cannot pass the session handshake accidentally, and stale HyperBit firmware reports an actionable version error instead of looking like an unexplained transport failure.

## Notification throughput

The microphone produces 8,000 samples per second at 4 bits per IMA-ADPCM sample, or about **4,000 ADPCM bytes per second**. A protocol-v2 microphone packet carries up to 17 audio bytes, so continuous speech needs roughly **236 device-to-PC notifications per second**.

Nordic's S113 GATTS default permits only one queued Handle Value Notification. Firmware r5 therefore uses a reviewed build-time CODAL override that configures a **12-entry GATTS notification queue** before `nrf_sdh_ble_enable()` and reserves additional lower RAM for that SoftDevice configuration. The wire format stays at the default 23-byte ATT MTU / 20-byte characteristic payload for Windows compatibility.

For the CODAL-UART-backed implementation, the same fail-closed build override also changes the locked upstream UART TX characteristic from `INDICATE` to `NOTIFY`. The build fails if the expected upstream source anchor is missing or appears more than once, and the archived override log records the exact SHA-256 of the patched UART source.

The 512-byte microphone ring remains the second layer of backpressure protection. `sendMic()` retries temporary notification-queue exhaustion; if transport stalls long enough to overrun the ring, the utterance is marked overflowed rather than silently pretending it is intact.

The release build fails if the locked CODAL revision changes unexpectedly, if either transport override is absent/misapplied, if the patched application RAM boundary is not used by the final ELF, or if less than 64 KiB of calculated CODAL heap capacity remains.

## Frame types

Every NUS write/notification is at most 20 bytes.

- `A0` — control frame
- `A1` — microphone audio frame
- `A2` — TTS audio frame
- `A3` — HELLO frame

### Microphone frame

`[A1 sequence length <up to 17 ADPCM bytes>]`

The microphone hardware is activated only while the micro:bit V2 gold logo is held. While held, compressed audio is continuously drained from a 512-byte ring buffer and transmitted in BLE-sized packets. On release the remaining bytes are flushed and the microphone hardware is deactivated.

The PC checks microphone sequence numbers. A packet gap is carried forward as an utterance warning rather than silently pretending the ADPCM stream was intact.

### TTS frame

`[A2 sequence length <up to 17 ADPCM bytes>]`

The PC splits TTS into segments of at most 512 ADPCM bytes. Each segment is split again into NUS-sized frames, and the next segment is not sent until the micro:bit acknowledges the previous segment. A sequence error aborts the active segment; a queued stale `TTS_END` cannot turn that abort into a false success.

## Control frame

Control frames begin with `A0`, followed by the HyperBit control code and arguments.

### Device -> PC

- `A0 10` gold-logo PTT start
- `A0 11 lo mid hi` PTT end (23-bit sample count; high bit of `hi` = overflow flag)
- `A0 12 protocol revision capabilities` firmware READY / identity
- `A0 13` A-button cancel/interrupt
- `A0 14` B-button replay request
- `A0 15 mm` mute changed
- `A0 16 ok` TTS segment finished/interrupted
- `A0 17 ok` Wukong I2C base-light status

### PC -> device

- `A0 30 ll hh ff` TTS segment start (`ff & 1` means first segment / reset ADPCM decoder)
- `A0 31` TTS segment end
- `A0 32` abort current TTS receive
- `A0 40 state` set physical agent state

## Connection-phase behavior

As soon as a raw BLE link appears, firmware freezes application animation on the currently rendered frame but **does not disable or restart the micro:bit V2 LED-matrix driver**. Until READY has successfully been queued, it performs no accelerometer sampling, Wukong I2C/Rainbow updates, microphone work, speaker PWM work, button interaction, or normal personality animation. Keeping CODAL's TIMER4-backed display lifecycle untouched avoids adding a second hardware-lifecycle transition during fragile Windows GATT setup.

A raw connection that never completes HELLO/READY is bounded. After roughly **38 seconds** firmware requests a GAP disconnect. If the SoftDevice still reports the raw link after roughly **2 additional seconds**, firmware calls the target reset path so the MCU/SoftDevice boots cleanly and advertises again.

After a validated session is established, an unexpected disconnect is surfaced to the PC agent. The normal voice launcher automatically scans and reconnects rather than hanging forever waiting for another utterance.

## Physical controls

- Hold gold logo: microphone ON / stream voice
- Release gold logo: microphone OFF / finish utterance
- A: cancel response or interrupt speaker playback
- B: replay the last PC-generated answer
- A+B: mute/unmute speaker output
