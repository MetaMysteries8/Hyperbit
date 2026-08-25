# HyperBit Instructions

## 1. Flash the firmware

Plug the **micro:bit V2 itself** into your Windows PC over USB. Copy `HyperBit.hex` onto the `MICROBIT` drive.

The Wukong is not flashed separately. HyperBit firmware runs on the micro:bit and contains the code that controls the Wukong board.

After flashing finishes, you can unplug USB and power the micro:bit from the Wukong battery.

## 2. Install the PC dependencies

Open a terminal in this folder and run:

```bat
py -3 -m pip install -r requirements.txt
```

If `py` is unavailable, use:

```bat
python -m pip install -r requirements.txt
```

The first speech-to-text run may download the configured faster-whisper model.

## 3. Set your Hyper API key

Keep the key on the PC. Do not put it in the firmware.

For the current Command Prompt window:

```bat
set HYPER_API_KEY=sk-hyper-your-key
```

Optional settings:

```bat
set HYPER_MODEL=deepseek-v4-flash
set HYPERBIT_TTS=sapi
```

`HYPERBIT_TTS=sapi` uses offline Windows speech synthesis. `HYPERBIT_TTS=gtts` uses Google TTS and requires internet access.

## 4. Run HyperBit

```bat
py -3 HyperBit.py
```

Then hold the micro:bit's gold logo, speak, and release it.

## Controls

- Hold gold logo: record voice.
- Release gold logo: send the recorded voice to the PC over Bluetooth.
- Built-in microphone: input.
- Built-in speaker: short spoken response.
- Wukong blue LEDs: connection/agent-state display.

## Troubleshooting

If the PC cannot find the board, make sure the micro:bit is powered, Bluetooth is enabled on Windows, and `HyperBit.hex` is actually flashed.

If Hyper returns an authentication error, check `HYPER_API_KEY`.

If speech recognition is slow on the first run, faster-whisper may still be downloading/loading its model.
