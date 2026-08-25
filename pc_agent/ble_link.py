from __future__ import annotations

import asyncio
from dataclasses import dataclass

from bleak import BleakClient, BleakScanner

# Standard Nordic UART Service (NUS). HyperBit no longer exposes the old
# 7f9a... three-characteristic custom service.
SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
RX_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # PC -> micro:bit
TX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # micro:bit -> PC

FRAME_CONTROL = 0xA0
FRAME_MIC = 0xA1
FRAME_TTS = 0xA2
FRAME_HELLO = 0xA3
PROTOCOL_VERSION = 2
AUDIO_PAYLOAD_BYTES = 17

EVT_PTT_START = 0x10
EVT_PTT_END = 0x11
EVT_READY = 0x12
EVT_CANCEL = 0x13
EVT_REPLAY = 0x14
EVT_MUTE_CHANGED = 0x15
EVT_TTS_SEGMENT_DONE = 0x16
EVT_WUKONG_STATUS = 0x17

CMD_TTS_START = 0x30
CMD_TTS_END = 0x31
CMD_TTS_ABORT = 0x32
CMD_SET_STATE = 0x40

STATE_IDLE = 1
STATE_LISTENING = 2
STATE_TRANSCRIBING = 3
STATE_THINKING = 4
STATE_SPEAKING = 5
STATE_ERROR = 6

TTS_SEGMENT_BYTES = 512
GATT_CONNECT_TIMEOUT_SECONDS = 35.0
GATT_RECOVERY_WAIT_SECONDS = 15.0
HELLO_TIMEOUT_SECONDS = 5.0


@dataclass
class Utterance:
    adpcm: bytes
    sample_count: int
    overflow: bool


class HyperBitBLE:
    def __init__(self, name_hint: str | None = None, address: str | None = None):
        self.name_hint = name_hint
        self.address = address
        self.client: BleakClient | None = None
        self.tx_char = None
        self.rx_char = None
        self._recv = bytearray()
        self._seq = None
        self._utterances: asyncio.Queue[Utterance] = asyncio.Queue()
        self._replay_requests: asyncio.Queue[None] = asyncio.Queue()
        self._loop = None
        self._cancel = asyncio.Event()
        self._ready = asyncio.Event()
        self._tts_done = asyncio.Event()
        self._tts_done_ok = True
        self._tx_lock = asyncio.Lock()

    async def _find(self):
        print("[ble] scanning 10 seconds...")
        found = await BleakScanner.discover(timeout=10.0, return_adv=True)
        candidates = []
        seen = []

        for _key, pair in found.items():
            device, adv = pair
            name = adv.local_name or device.name or ""
            service_uuids = [u.lower() for u in (adv.service_uuids or [])]
            seen.append((name or "<unnamed>", device.address, service_uuids))

            if self.address and device.address.lower() == self.address.lower():
                return device
            if self.name_hint and self.name_hint.lower() in name.lower():
                candidates.append(device)
                continue
            if SERVICE_UUID.lower() in service_uuids:
                candidates.append(device)
                continue
            if not self.name_hint and ("micro:bit" in name.lower() or "microbit" in name.lower()):
                candidates.append(device)

        if not candidates:
            print("[ble] no HyperBit candidate matched. Devices seen by Windows:")
            if not seen:
                print("  (none)")
            for name, address, services in seen[:40]:
                s = ", ".join(services) if services else "<no advertised services>"
                print(f"  {name}  {address}  services={s}")
            raise RuntimeError(
                "No advertising HyperBit/micro:bit found. If the board is listed above, "
                "send that block back so the firmware/advertising can be diagnosed."
            )

        device = candidates[0]
        print(f"[ble] selected {device.name or 'micro:bit'} ({device.address})")
        return device

    async def _disconnect_partial(self):
        if not self.client:
            return
        try:
            if self.client.is_connected:
                await asyncio.wait_for(self.client.disconnect(), timeout=5.0)
        except Exception:
            pass
        finally:
            self.client = None
            self.tx_char = None
            self.rx_char = None
            self._ready.clear()

    def _resolve_nus_chars(self):
        assert self.client is not None
        svc = self.client.services.get_service(SERVICE_UUID)
        if svc is None:
            return None
        tx = svc.get_characteristic(TX_UUID)
        rx = svc.get_characteristic(RX_UUID)
        if not all((tx, rx)):
            return None
        return tx, rx

    async def _write_frame(self, payload: bytes):
        if len(payload) > 20:
            raise ValueError(f"NUS frame too large: {len(payload)} bytes")
        assert self.client and self.rx_char
        props = {p.lower() for p in self.rx_char.properties}
        response = "write-without-response" not in props
        await self.client.write_gatt_char(self.rx_char, payload, response=response)

    async def connect(self):
        # Scan once and preserve the concrete Windows BLEDevice. A failed service
        # discovery can leave the board connected and therefore not advertising.
        dev = await self._find()

        attempts = [
            (True, "Windows cached services"),
            (False, "fresh/uncached services after firmware recovery"),
            (False, "fresh/uncached services retry"),
        ]
        last_error: BaseException | None = None

        for attempt, (use_cache, label) in enumerate(attempts, 1):
            if attempt > 1:
                print(
                    f"[ble] retry {attempt}/{len(attempts)}: reusing {dev.address}; "
                    f"waiting {GATT_RECOVERY_WAIT_SECONDS:.0f}s for firmware BLE recovery..."
                )
                await asyncio.sleep(GATT_RECOVERY_WAIT_SECONDS)

            print(
                f"[ble] connecting to {dev.name or 'micro:bit'} ({dev.address}) "
                f"using {label}"
            )

            self.client = BleakClient(
                dev,
                timeout=GATT_CONNECT_TIMEOUT_SECONDS,
                pair=False,
                winrt={"use_cached_services": use_cache},
            )

            try:
                await self.client.connect()

                chars = self._resolve_nus_chars()
                if chars is None:
                    if use_cache:
                        print("[ble] cached service layout is stale; retrying uncached")
                        await self._disconnect_partial()
                        continue

                    print("[ble] services present on connected device:")
                    for service in self.client.services:
                        print(" ", service.uuid)
                    await self._disconnect_partial()
                    raise RuntimeError("The board connected, but Nordic UART Service is missing.")

                self.tx_char, self.rx_char = chars
                self._loop = asyncio.get_running_loop()
                self._ready.clear()

                # Subscribe first, then explicitly tell firmware that the NUS
                # application session is ready. The firmware does not inspect
                # CCCDs during Windows service discovery anymore.
                await self.client.start_notify(self.tx_char, self._nus_notify)
                await self._write_frame(bytes([FRAME_HELLO, PROTOCOL_VERSION]))

                try:
                    await asyncio.wait_for(self._ready.wait(), timeout=HELLO_TIMEOUT_SECONDS)
                except asyncio.TimeoutError as exc:
                    raise RuntimeError("Bluetooth connected, but HyperBit HELLO/READY handshake timed out") from exc

                print(f"[ble] connected over Nordic UART Service; HyperBit protocol v{PROTOCOL_VERSION}")
                await self.set_state(STATE_IDLE)
                return

            except (TimeoutError, asyncio.TimeoutError) as exc:
                last_error = exc
                print("[ble] Windows timed out while establishing the BLE service session.")
                await self._disconnect_partial()
            except RuntimeError as exc:
                last_error = exc
                print(f"[ble] session attempt failed: {exc}")
                await self._disconnect_partial()
            except Exception as exc:
                last_error = exc
                print(f"[ble] connection attempt failed: {type(exc).__name__}: {exc}")
                await self._disconnect_partial()

        raise RuntimeError(
            "Windows found the micro:bit but could not establish the Nordic UART Service session "
            "after three attempts. The firmware now disables the LED matrix and all peripheral "
            "activity during the raw connection window, so repeated failure here points at the "
            "BLE/security/runtime layer rather than the fluid animation."
        ) from last_error

    def _nus_notify(self, _sender, data: bytearray):
        if not data or self._loop is None:
            return

        frame_type = data[0]

        if frame_type == FRAME_MIC:
            if len(data) < 3:
                return
            seq = data[1]
            n = min(data[2], len(data) - 3)
            payload = bytes(data[3:3 + n])
            if self._seq is not None and seq != ((self._seq + 1) & 0xFF):
                print(f"[ble] mic packet gap: expected {(self._seq + 1) & 0xFF}, got {seq}")
            self._seq = seq
            self._recv.extend(payload)
            return

        if frame_type != FRAME_CONTROL or len(data) < 2:
            return

        code = data[1]
        a = data[2] if len(data) >= 3 else 0
        b = data[3] if len(data) >= 4 else 0
        c = data[4] if len(data) >= 5 else 0

        if code == EVT_PTT_START:
            self._recv.clear()
            self._seq = None
            self._cancel.clear()
            print("[device] gold logo down: microphone ON")

        elif code == EVT_PTT_END:
            samples = a | (b << 8) | ((c & 0x7F) << 16)
            overflow = bool(c & 0x80)
            utt = Utterance(bytes(self._recv), samples, overflow)
            self._loop.call_soon_threadsafe(self._utterances.put_nowait, utt)
            print(f"[device] gold logo up: microphone OFF; {len(self._recv)} ADPCM bytes")

        elif code == EVT_READY:
            if a != PROTOCOL_VERSION:
                print(f"[device] protocol mismatch: firmware={a}, pc={PROTOCOL_VERSION}")
            else:
                print(f"[device] firmware ready; NUS transport protocol v{a}")
            self._loop.call_soon_threadsafe(self._ready.set)

        elif code == EVT_CANCEL:
            print("[device] A: cancel/interrupt")
            self._loop.call_soon_threadsafe(self._cancel.set)

        elif code == EVT_REPLAY:
            print("[device] B: replay last answer")
            self._loop.call_soon_threadsafe(self._replay_requests.put_nowait, None)

        elif code == EVT_MUTE_CHANGED:
            print(f"[device] A+B: {'muted' if a else 'unmuted'}")

        elif code == EVT_TTS_SEGMENT_DONE:
            self._tts_done_ok = bool(a)
            self._loop.call_soon_threadsafe(self._tts_done.set)

        elif code == EVT_WUKONG_STATUS:
            print(f"[device] Wukong I2C base LEDs: {'OK' if a else 'NOT RESPONDING'}")

    async def next_utterance(self):
        return await self._utterances.get()

    async def next_replay_request(self):
        await self._replay_requests.get()

    def cancelled(self):
        return self._cancel.is_set()

    def clear_cancel(self):
        self._cancel.clear()

    async def _write_control(self, code: int, a: int = 0, b: int = 0, c: int = 0, include_all: bool = False):
        if include_all:
            payload = bytes([FRAME_CONTROL, code & 0xFF, a & 0xFF, b & 0xFF, c & 0xFF])
        elif c:
            payload = bytes([FRAME_CONTROL, code & 0xFF, a & 0xFF, b & 0xFF, c & 0xFF])
        elif b:
            payload = bytes([FRAME_CONTROL, code & 0xFF, a & 0xFF, b & 0xFF])
        elif a:
            payload = bytes([FRAME_CONTROL, code & 0xFF, a & 0xFF])
        else:
            payload = bytes([FRAME_CONTROL, code & 0xFF])
        await self._write_frame(payload)

    async def set_state(self, state: int):
        await self._write_control(CMD_SET_STATE, state)

    async def abort_tts(self):
        if self.client and self.client.is_connected:
            await self._write_control(CMD_TTS_ABORT)

    async def _send_tts_segment(self, segment: bytes, first: bool):
        self._tts_done.clear()
        self._tts_done_ok = True

        # Start frame is always fixed-width so a zero high-byte/first flag is not
        # accidentally omitted by compact control encoding.
        await self._write_frame(
            bytes([
                FRAME_CONTROL,
                CMD_TTS_START,
                len(segment) & 0xFF,
                (len(segment) >> 8) & 0xFF,
                1 if first else 0,
            ])
        )

        seq = 0
        for off in range(0, len(segment), AUDIO_PAYLOAD_BYTES):
            if self.cancelled():
                await self.abort_tts()
                return False
            chunk = segment[off:off + AUDIO_PAYLOAD_BYTES]
            await self._write_frame(bytes([FRAME_TTS, seq, len(chunk)]) + chunk)
            seq = (seq + 1) & 0xFF
            await asyncio.sleep(0.003)

        await self._write_control(CMD_TTS_END)

        try:
            await asyncio.wait_for(self._tts_done.wait(), timeout=8.0)
        except asyncio.TimeoutError:
            raise RuntimeError("micro:bit did not acknowledge the TTS segment")

        return self._tts_done_ok and not self.cancelled()

    async def send_tts(self, adpcm: bytes):
        async with self._tx_lock:
            first = True
            for off in range(0, len(adpcm), TTS_SEGMENT_BYTES):
                if self.cancelled():
                    return False
                segment = adpcm[off:off + TTS_SEGMENT_BYTES]
                if not await self._send_tts_segment(segment, first):
                    return False
                first = False
            return True

    async def close(self):
        if self.client:
            try:
                if self.client.is_connected:
                    await self.client.disconnect()
            finally:
                self.client = None
                self.tx_char = None
                self.rx_char = None
