# HyperBit BLE protocol

HyperBit uses the standard Nordic UART Service (NUS) UUID layout instead of the old custom three-characteristic service.

| NUS item | UUID | Direction |
|---|---|---|
| Service | `6e400001-b5a3-f393-e0a9-e50e24dcca9e` | — |
| RX | `6e400002-b5a3-f393-e0a9-e50e24dcca9e` | PC -> micro:bit write |
| TX | `6e400003-b5a3-f393-e0a9-e50e24dcca9e` | micro:bit -> PC notify |

BLE still uses GATT underneath because that is the application-data transport exposed by the micro:bit/Windows BLE stack. HyperBit no longer invents its own service layout: all application packets are multiplexed over the conventional two-characteristic NUS shape.

Audio is 8 kHz mono IMA ADPCM. Every new microphone utterance starts with predictor=0/index=0. TTS is one continuous ADPCM stream split into acknowledged 512-byte segments; the decoder resets only on the first segment.

## Session handshake

The PC first subscribes to NUS TX, then writes:

`[A3 02]`

- `A3` = HELLO frame
- `02` = HyperBit protocol version 2

Only after that write does the firmware consider the application session ready. A raw Bluetooth link alone is not enough.

## Frame types

Every NUS write/notification is at most 20 bytes.

- `A0` — control frame
- `A1` — microphone audio frame
- `A2` — TTS audio frame
- `A3` — HELLO frame

### Microphone frame

`[A1 sequence length <up to 17 ADPCM bytes>]`

The microphone hardware is activated only while the micro:bit V2 gold logo is held. While held, compressed audio is continuously drained from a 512-byte ring buffer and transmitted in BLE-sized packets. On release the remaining bytes are flushed and the microphone hardware is deactivated.

### TTS frame

`[A2 sequence length <up to 17 ADPCM bytes>]`

The PC splits TTS into segments of at most 512 ADPCM bytes. Each segment is split again into NUS-sized frames, and the next segment is not sent until the micro:bit acknowledges the previous segment.

## Control frame

Control frames begin with `A0`, followed by the existing HyperBit control code and arguments.

### Device -> PC

- `A0 10` gold-logo PTT start
- `A0 11 lo mid hi` PTT end (23-bit sample count; high bit of `hi` = overflow flag)
- `A0 12 02 ...` firmware ready / protocol v2
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

While a raw BLE link exists but the HELLO handshake is not complete, firmware disables the 5x5 LED matrix refresh driver and performs no fluid animation, accelerometer reads, Wukong updates, microphone work, or speaker PWM work. Connection setup gets priority over personality/animation.

## Physical controls

- Hold gold logo: microphone ON / stream voice
- Release gold logo: microphone OFF / finish utterance
- A: cancel response or interrupt speaker playback
- B: replay the last PC-generated answer
- A+B: mute/unmute speaker output
