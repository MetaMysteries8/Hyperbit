# HyperBit BLE protocol

Service: `7f9a0001-4c1d-4b8f-9a31-c62d5e8b1f70`

| Characteristic | UUID | Direction |
|---|---|---|
| Mic ADPCM | `7f9a0002-4c1d-4b8f-9a31-c62d5e8b1f70` | micro:bit -> PC notify |
| Speaker ADPCM | `7f9a0003-4c1d-4b8f-9a31-c62d5e8b1f70` | PC -> micro:bit write |
| Control | `7f9a0004-4c1d-4b8f-9a31-c62d5e8b1f70` | both |

Audio is 8 kHz mono IMA ADPCM, starting each utterance with predictor=0/index=0.

Mic/Speaker data packets are `[sequence byte][up to 19 ADPCM bytes]`.

Device -> PC control:
- `10` PTT start
- `11 ss ss oo` PTT end (`uint16 sample_count`, overflow byte)
- `12` firmware ready

PC -> device:
- `30 ll ll` TTS start
- `31` TTS end
- `40 state` set physical state

States:
1 idle, 2 listening, 3 transcribing, 4 thinking, 5 speaking, 6 error.
