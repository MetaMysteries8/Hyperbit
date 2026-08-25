# HyperBit Info

HyperBit is a PC-hosted voice AI agent with a **BBC micro:bit V2 + ELECFREAKS Wukong** as its physical wireless body.

## micro:bit V2

- Gold capacitive logo = push-to-talk.
- Built-in microphone = speech capture.
- Built-in speaker = spoken responses.
- A = interrupt/cancel.
- B = replay.
- A+B = mute toggle.
- BLE = bidirectional compressed audio/control over Nordic UART Service.

The microphone hardware is only activated while the gold logo is held.

## Wukong

Wukong is actively driven by the firmware rather than merely serving as a battery holder:

- built-in battery powers the handheld agent,
- eight blue base LEDs are controlled by Wukong's I2C controller,
- four Rainbow LEDs on P16 are used for visible agent-state colors,
- boot performs a visible Wukong self-test.

## Windows PC

The PC is the agent's main home:

- faster-whisper for local speech-to-text,
- Charm Hyper for the model/tool loop,
- durable memory and sandboxed workspace,
- Windows SAPI for local TTS,
- Bleak for Bluetooth.

The Hyper API key remains on the PC.

## BLE transport

HyperBit uses the standard Nordic UART Service UUID layout rather than the earlier custom three-characteristic `7f9a...` service. There are only two application characteristics: NUS RX for PC -> device writes and NUS TX for device -> PC notifications.

BLE/GATT still exists underneath because it is the application-data mechanism exposed by the micro:bit SoftDevice and Windows BLE APIs, but HyperBit no longer invents a bespoke GATT shape.

After Windows connects and subscribes to NUS TX, it sends a HyperBit protocol HELLO frame. The firmware only becomes interactive after that explicit HELLO/READY handshake.

During the raw Bluetooth connection window the 5x5 LED matrix refresh driver is disabled and firmware performs no face animation, accelerometer reads, Wukong updates, microphone work, or speaker PWM work. Connection setup gets priority.

## Audio transport

Audio is 8 kHz mono IMA ADPCM.

Input is streamed in BLE-sized chunks while push-to-talk is held. The microphone ring is 512 bytes and is continuously drained rather than holding a whole utterance in RAM.

Output is segmented into <=512-byte ADPCM pieces, then each piece is packetized into <=20-byte NUS frames and acknowledged before the next piece is sent. This intentionally trades a little more packet overhead for several KiB of RAM headroom on the micro:bit.

## Release verification

Automatic releases are only published after the configured Python syntax checks, Bandit analysis, dependency vulnerability audit, ClamAV scans, successful micro:bit V2 firmware compilation, byte-for-byte source-injection verification, and BLE security-config verification complete.

Each release also includes `BUILD_PROVENANCE.txt`, containing the exact Git commit, source SHA-256 hashes, CODAL commit, requested CODAL version, and linker memory summary used for that HEX.

Automated scanning improves release hygiene but cannot mathematically prove that software contains no possible bug or malicious behavior.
