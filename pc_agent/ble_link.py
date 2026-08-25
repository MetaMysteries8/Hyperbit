from __future__ import annotations

import asyncio
from dataclasses import dataclass

from bleak import BleakClient, BleakScanner

SERVICE_UUID = "7f9a0001-4c1d-4b8f-9a31-c62d5e8b1f70"
MIC_UUID = "7f9a0002-4c1d-4b8f-9a31-c62d5e8b1f70"
SPEAKER_UUID = "7f9a0003-4c1d-4b8f-9a31-c62d5e8b1f70"
CONTROL_UUID = "7f9a0004-4c1d-4b8f-9a31-c62d5e8b1f70"

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

TTS_SEGMENT_BYTES = 4096


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
        self.mic_char = None
        self.speaker_char = None
        self.control_char = None
        self._recv = bytearray()
        self._seq = None
        self._utterances: asyncio.Queue[Utterance] = asyncio.Queue()
        self._replay_requests: asyncio.Queue[None] = asyncio.Queue()
        self._loop = None
        self._cancel = asyncio.Event()
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

    def _resolve_hyperbit_chars(self):
        assert self.client is not None
        svc = self.client.services.get_service(SERVICE_UUID)
        if svc is None:
            return None
        mic = svc.get_characteristic(MIC_UUID)
        speaker = svc.get_characteristic(SPEAKER_UUID)
        control = svc.get_characteristic(CONTROL_UUID)
        if not all((mic, speaker, control)):
            return None
        return mic, speaker, control

    async def connect(self):
        # Discover once and KEEP this BLEDevice object. A failed GATT attempt can
        # leave the micro:bit connected but no longer advertising, so rescanning
        # between retries makes Windows lose the exact device we already found.
        dev = await self._find()

        # Prefer Windows' cache first because it avoids a full uncached attribute
        # walk when the layout is already known. If the cached layout is stale or
        # missing HyperBit, retry uncached. Do not request only SERVICE_UUID here:
        # WinRT uses a separate GetGattServicesForUuidAsync path for that filter,
        # which has proven less useful for this DIY peripheral during recovery.
        attempts = [
            (True, "Windows cached GATT"),
            (False, "fresh/uncached full GATT"),
            (True, "cached GATT retry"),
        ]
        last_error: BaseException | None = None

        for attempt, (use_cache, label) in enumerate(attempts, 1):
            if attempt > 1:
                print(
                    f"[ble] retry {attempt}/{len(attempts)}: reusing {dev.address}; "
                    f"waiting 5 seconds before {label}..."
                )
                await asyncio.sleep(5.0)

            print(
                f"[ble] connecting to {dev.name or 'micro:bit'} ({dev.address}) "
                f"using {label}"
            )

            self.client = BleakClient(
                dev,
                timeout=35.0,
                pair=False,
                winrt={"use_cached_services": use_cache},
            )

            try:
                await self.client.connect()

                chars = self._resolve_hyperbit_chars()
                if chars is None:
                    if use_cache:
                        print("[ble] cached GATT connected but HyperBit service/layout was stale; retrying uncached")
                        await self._disconnect_partial()
                        continue

                    print("[ble] services present on connected device:")
                    for service in self.client.services:
                        print(" ", service.uuid)
                    await self._disconnect_partial()
                    raise RuntimeError("The board connected, but the HyperBit BLE service/layout is missing.")

                self.mic_char, self.speaker_char, self.control_char = chars
                self._loop = asyncio.get_running_loop()

                await self.client.start_notify(self.mic_char, self._mic_notify)
                await self.client.start_notify(self.control_char, self._control_notify)
                print("[ble] connected; notifications armed")
                await self.set_state(STATE_IDLE)
                return

            except (TimeoutError, asyncio.TimeoutError) as exc:
                last_error = exc
                print("[ble] Windows timed out while establishing the GATT session.")
                await self._disconnect_partial()
            except RuntimeError:
                raise
            except Exception as exc:
                last_error = exc
                print(f"[ble] connection attempt failed: {type(exc).__name__}: {exc}")
                await self._disconnect_partial()

        raise RuntimeError(
            "Windows found the micro:bit but could not establish a usable HyperBit GATT session "
            "after three attempts. The same BLEDevice was reused, so this is no longer a "
            "re-advertising/rescan failure. If the micro:bit face also stops animating during "
            "the attempt, the firmware/SoftDevice side is stalling and should be diagnosed next."
        ) from last_error

    def _mic_notify(self, _sender, data: bytearray):
        if not data:
            return
        seq = data[0]
        payload = bytes(data[1:])
        if self._seq is not None and seq != ((self._seq + 1) & 0xFF):
            print(f"[ble] mic packet gap: expected {(self._seq + 1) & 0xFF}, got {seq}")
        self._seq = seq
        self._recv.extend(payload)

    def _control_notify(self, _sender, data: bytearray):
        if not data or self._loop is None:
            return

        code = data[0]

        if code == EVT_PTT_START:
            self._recv.clear()
            self._seq = None
            self._cancel.clear()
            print("[device] gold logo down: microphone ON")

        elif code == EVT_PTT_END:
            samples = 0
            overflow = False
            if len(data) >= 4:
                samples = data[1] | (data[2] << 8) | ((data[3] & 0x7F) << 16)
                overflow = bool(data[3] & 0x80)
            utt = Utterance(bytes(self._recv), samples, overflow)
            self._loop.call_soon_threadsafe(self._utterances.put_nowait, utt)
            print(f"[device] gold logo up: microphone OFF; {len(self._recv)} ADPCM bytes")

        elif code == EVT_READY:
            print("[device] firmware ready")

        elif code == EVT_CANCEL:
            print("[device] A: cancel/interrupt")
            self._loop.call_soon_threadsafe(self._cancel.set)

        elif code == EVT_REPLAY:
            print("[device] B: replay last answer")
            self._loop.call_soon_threadsafe(self._replay_requests.put_nowait, None)

        elif code == EVT_MUTE_CHANGED:
            muted = bool(data[1]) if len(data) >= 2 else False
            print(f"[device] A+B: {'muted' if muted else 'unmuted'}")

        elif code == EVT_TTS_SEGMENT_DONE:
            self._tts_done_ok = bool(data[1]) if len(data) >= 2 else True
            self._loop.call_soon_threadsafe(self._tts_done.set)

        elif code == EVT_WUKONG_STATUS:
            ok = bool(data[1]) if len(data) >= 2 else False
            print(f"[device] Wukong I2C base LEDs: {'OK' if ok else 'NOT RESPONDING'}")

    async def next_utterance(self):
        return await self._utterances.get()

    async def next_replay_request(self):
        await self._replay_requests.get()

    def cancelled(self):
        return self._cancel.is_set()

    def clear_cancel(self):
        self._cancel.clear()

    async def _write_control(self, payload: bytes):
        assert self.client and self.control_char
        props = {p.lower() for p in self.control_char.properties}
        response = "write-without-response" not in props
        await self.client.write_gatt_char(self.control_char, payload, response=response)

    async def set_state(self, state: int):
        await self._write_control(bytes([CMD_SET_STATE, state & 0xFF]))

    async def abort_tts(self):
        if self.client and self.client.is_connected:
            await self._write_control(bytes([CMD_TTS_ABORT]))

    async def _send_tts_segment(self, segment: bytes, first: bool):
        assert self.client and self.speaker_char

        self._tts_done.clear()
        self._tts_done_ok = True

        await self._write_control(
            bytes([CMD_TTS_START, len(segment) & 0xFF, (len(segment) >> 8) & 0xFF, 1 if first else 0])
        )

        props = {p.lower() for p in self.speaker_char.properties}
        response = "write-without-response" not in props
        seq = 0

        for off in range(0, len(segment), 19):
            if self.cancelled():
                await self.abort_tts()
                return False
            packet = bytes([seq]) + segment[off:off + 19]
            await self.client.write_gatt_char(self.speaker_char, packet, response=response)
            seq = (seq + 1) & 0xFF
            await asyncio.sleep(0.003)

        await self._write_control(bytes([CMD_TTS_END]))

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
