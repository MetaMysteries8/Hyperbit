# HyperBit BLE protocol

Service: `7f9a0001-4c1d-4b8f-9a31-c62d5e8b1f70`

| Characteristic | UUID | Direction |
|---|---|---|
| Mic ADPCM | `7f9a0002-4c1d-4b8f-9a31-c62d5e8b1f70` | micro:bit -> PC notify |
| Speaker ADPCM | `7f9a0003-4c1d-4b8f-9a31-c62d5e8b1f70` | PC -> micro:bit write |
| Control | `7f9a0004-4c1d-4b8f-9a31-c62d5e8b1f70` | both |

Audio is 8 kHz mono IMA ADPCM. Every new microphone utterance starts with predictor=0/index=0. TTS is one continuous ADPCM stream split into acknowledged segments; the decoder resets only on the first segment.

## Mic packets

`[sequence byte][up to 19 ADPCM bytes]`

The microphone hardware is activated only while the micro:bit V2 gold logo is held. While held, compressed mic audio is continuously drained from a small ring buffer and transmitted in BLE-sized packets. On release the remaining bytes are flushed and the mic hardware is deactivated.

## Speaker packets

TTS is not sent as one huge micro:bit file. The PC splits it into segments of at most 4096 ADPCM bytes, then each segment is split again into 19-byte BLE payloads.

The next segment is not sent until the micro:bit acknowledges that the current segment finished playing.

## Device -> PC control

- `10` gold-logo PTT start
- `11 lo mid hi` PTT end (23-bit sample count; high bit of `hi` = overflow flag)
- `12` firmware ready
- `13` A-button cancel/interrupt
- `14` B-button replay request
- `15 mm` mute changed
- `16 ok` TTS segment finished/interrupted
- `17 ok` Wukong I2C base-light status

## PC -> device control

- `30 ll ll ff` TTS segment start (`ff & 1` means first segment / reset ADPCM decoder)
- `31` TTS segment end
- `32` abort current TTS receive
- `40 state` set physical agent state

## Physical controls

- Hold gold logo: microphone ON / stream voice
- Release gold logo: microphone OFF / finish utterance
- A: cancel response or interrupt speaker playback
- B: replay the last PC-generated answer
- A+B: mute/unmute speaker output
