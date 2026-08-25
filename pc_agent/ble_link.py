from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

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
MIN_FIRMWARE_REVISION = 3

CAP_CONNECTION_ISOLATION = 0x01
CAP_SAFE_RAINBOW_PWM = 0x02
CAP_SEGMENTED_TTS = 0x04
REQUIRED_CAPABILITIES = CAP_CONNECTION_ISOLATION | CAP_SEGMENTED_TTS

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


class BLEDisconnectedError(RuntimeError):
    """Raised when a previously validated HyperBit session disappears."""


@dataclass
class Utterance:
    adpcm: bytes
    sample_count: int
    overflow: bool


@dataclass
class Candidate:
    # Keep the advertisement-derived identity next to the concrete BLEDevice.
    # Windows can expose adv.local_name while BLEDevice.name is blank/different.
    device: Any
    display_name: str
    is_microbit: bool


class HyperBitBLE:
    def __init__(self, name_hint: str | None = None, address: str | None = None):
        self.name_hint = name_hint
        self.address = address
        self.client: BleakClient | None = None
        self.tx_char = None
        self.rx_char = None

        self.firmware_revision = 0
        self.capabilities = 0

        self._recv = bytearray()
        self._seq = None
        self._mic_gap = False
        self._utterances: asyncio.Queue[Utterance] = asyncio.Queue()
        self._replay_requests: asyncio.Queue[None] = asyncio.Queue()
        self._loop = None
        self._cancel = asyncio.Event()
        self._ready = asyncio.Event()
        self._ready_error: str | None = None
        self._tts_done = asyncio.Event()
        self._tts_done_ok = True
        self._disconnect_event = asyncio.Event()
        self._tx_lock = asyncio.Lock()
        self._session_active = False
        self._closing = False

    @staticmethod
    def _looks_like_microbit(name: str) -> bool:
        n = name.lower()
        return "micro:bit" in n or "microbit" in n

    @staticmethod
    def _clear_queue(queue: asyncio.Queue):
        while True:
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                return

    def _reset_runtime_state(self):
        self._recv.clear()
        self._seq = None
        self._mic_gap = False
        self._cancel.clear()
        self._ready.clear()
        self._ready_error = None
        self._tts_done.clear()
        self._tts_done_ok = True
        self.firmware_revision = 0
        self.capabilities = 0
        self._clear_queue(self._utterances)
        self._clear_queue(self._replay_requests)

    async def _find_candidates(self):
        """Return BLE candidates with their advertisement-derived classification.

        NUS is a standard/shared service, so advertising it does not prove a
        device is HyperBit. Explicit address/name hints take precedence. Without
        hints, micro:bit-looking advertisements are tried before generic NUS
        peripherals and every candidate must pass HyperBit HELLO/READY.
        """
        print("[ble] scanning 10 seconds...")
        found = await BleakScanner.discover(timeout=10.0, return_adv=True)
        seen = []
        exact_address: list[Candidate] = []
        name_matches: list[Candidate] = []
        microbits: list[Candidate] = []
        generic_nus: list[Candidate] = []

        for _key, pair in found.items():
            device, adv = pair
            display_name = adv.local_name or device.name or ""
            service_uuids = [u.lower() for u in (adv.service_uuids or [])]
            is_microbit = self._looks_like_microbit(display_name)
            candidate = Candidate(device, display_name or "<unnamed>", is_microbit)
            seen.append((candidate.display_name, device.address, service_uuids))

            if self.address and device.address.lower() == self.address.lower():
                exact_address.append(candidate)
                continue

            if self.name_hint:
                if self.name_hint.lower() in display_name.lower():
                    name_matches.append(candidate)
                continue

            if is_microbit:
                microbits.append(candidate)
                continue

            if SERVICE_UUID.lower() in service_uuids:
                generic_nus.append(candidate)

        if self.address:
            candidates = exact_address
        elif self.name_hint:
            candidates = name_matches
        else:
            candidates = microbits + generic_nus

        # Windows can surface one peripheral through multiple discovery records.
        # Keep ranking order while deduplicating by address.
        unique: list[Candidate] = []
        used_addresses = set()
        for candidate in candidates:
            key = candidate.device.address.lower()
            if key in used_addresses:
                continue
            used_addresses.add(key)
            unique.append(candidate)

        if not unique:
            print("[ble] no HyperBit candidate matched. Devices seen by Windows:")
            if not seen:
                print("  (none)")
            for name, address, services in seen[:40]:
                s = ", ".join(services) if services else "<no advertised services>"
                print(f"  {name}  {address}  services={s}")
            raise RuntimeError(
                "No advertising HyperBit/micro:bit found. If the board is listed above, "
                "send that block back so firmware/advertising can be diagnosed."
            )

        print(f"[ble] {len(unique)} candidate(s) will be validated with HyperBit HELLO")
        for index, candidate in enumerate(unique, 1):
            kind = "micro:bit" if candidate.is_microbit else "generic NUS"
            print(f"  [{index}] {candidate.display_name} ({candidate.device.address}) [{kind}]")
        return unique

    def _mark_unexpected_disconnect(self):
        if self._closing or not self._session_active:
            return
        self._session_active = False
        self._cancel.set()
        self._disconnect_event.set()
        print("[ble] HyperBit disconnected unexpectedly")

    def _on_disconnected(self, _client):
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._mark_unexpected_disconnect)

    async def _disconnect_partial(self):
        self._session_active = False
        client = self.client
        self.client = None
        self.tx_char = None
        self.rx_char = None
        self._ready.clear()
        if not client:
            return
        try:
            if client.is_connected:
                await asyncio.wait_for(client.disconnect(), timeout=5.0)
        except Exception:
            pass

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
        if self.client is None or self.rx_char is None:
            raise BLEDisconnectedError("HyperBit BLE session is not connected")

        props = {p.lower() for p in self.rx_char.properties}
        response = "write-without-response" not in props
        try:
            await self.client.write_gatt_char(self.rx_char, payload, response=response)
        except Exception as exc:
            if self._session_active or self._disconnect_event.is_set() or not self.client.is_connected:
                self._mark_unexpected_disconnect()
                raise BLEDisconnectedError("HyperBit disconnected during BLE write") from exc
            raise

    async def _try_candidate(self, candidate: Candidate, candidate_index: int, candidate_count: int):
        dev = candidate.device
        # Service migration makes stale Windows caches especially unhelpful. Start
        # uncached, recover uncached once more, then keep cache as a final fallback.
        attempts = [
            (False, "fresh/uncached services"),
            (False, "fresh/uncached services after firmware recovery"),
            (True, "Windows cached-services fallback"),
        ]
        last_error: BaseException | None = None

        for attempt, (use_cache, label) in enumerate(attempts, 1):
            if attempt > 1:
                print(
                    f"[ble] retry {attempt}/{len(attempts)} for {dev.address}: "
                    f"waiting {GATT_RECOVERY_WAIT_SECONDS:.0f}s for BLE recovery..."
                )
                await asyncio.sleep(GATT_RECOVERY_WAIT_SECONDS)

            print(
                f"[ble] candidate {candidate_index}/{candidate_count}: connecting to "
                f"{candidate.display_name} ({dev.address}) using {label}"
            )

            self.client = BleakClient(
                dev,
                timeout=GATT_CONNECT_TIMEOUT_SECONDS,
                pair=False,
                disconnected_callback=self._on_disconnected,
                winrt={"use_cached_services": use_cache},
            )

            try:
                await self.client.connect()

                chars = self._resolve_nus_chars()
                if chars is None:
                    print("[ble] candidate has no usable Nordic UART Service")
                    await self._disconnect_partial()
                    if use_cache:
                        return False, RuntimeError("Nordic UART Service is missing")
                    continue

                self.tx_char, self.rx_char = chars
                self._loop = asyncio.get_running_loop()
                self._ready.clear()
                self._ready_error = None

                # NUS is shared by many products. Subscription + protocol HELLO is
                # the actual identity check. Firmware accepts HELLO only after the
                # TX CCCD has been enabled by start_notify().
                await self.client.start_notify(self.tx_char, self._nus_notify)
                await self._write_frame(bytes([FRAME_HELLO, PROTOCOL_VERSION]))

                try:
                    await asyncio.wait_for(self._ready.wait(), timeout=HELLO_TIMEOUT_SECONDS)
                except asyncio.TimeoutError as exc:
                    last_error = RuntimeError(
                        "NUS connected, but this device did not answer HyperBit HELLO"
                    )
                    await self._disconnect_partial()

                    # Preserve the classification obtained from adv.local_name.
                    # Generic NUS devices get one identity attempt; likely
                    # micro:bits and explicit hints receive the recovery retries.
                    if not candidate.is_microbit and not self.address and not self.name_hint:
                        print("[ble] generic NUS device did not answer HyperBit HELLO; moving on")
                        return False, last_error
                    continue

                if self._ready_error:
                    last_error = RuntimeError(self._ready_error)
                    print(f"[ble] candidate rejected: {self._ready_error}")
                    await self._disconnect_partial()
                    # A stale HyperBit is definitely the selected device; repeating
                    # the same incompatible handshake will not repair its firmware.
                    return False, last_error

                if not self.client.is_connected:
                    raise BLEDisconnectedError("HyperBit disconnected immediately after READY")

                self._session_active = True
                self._disconnect_event.clear()
                self._cancel.clear()
                print(
                    f"[ble] HyperBit validated: protocol v{PROTOCOL_VERSION}, "
                    f"firmware r{self.firmware_revision}, capabilities=0x{self.capabilities:02x}"
                )
                await self.set_state(STATE_IDLE)
                return True, None

            except BLEDisconnectedError as exc:
                last_error = exc
                print(f"[ble] session dropped during setup: {exc}")
                await self._disconnect_partial()
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

        return False, last_error

    async def connect(self):
        self._closing = False
        self._session_active = False
        self._disconnect_event.clear()
        self._reset_runtime_state()
        self._loop = asyncio.get_running_loop()

        candidates = await self._find_candidates()
        last_error: BaseException | None = None

        for index, candidate in enumerate(candidates, 1):
            ok, error = await self._try_candidate(candidate, index, len(candidates))
            if ok:
                return
            if error is not None:
                last_error = error
            if index < len(candidates):
                print("[ble] candidate did not validate as HyperBit; trying next candidate...")

        raise RuntimeError(
            "Windows found Bluetooth candidates but none established a usable HyperBit NUS "
            "HELLO/READY session. If a candidate reports an old firmware revision, flash the "
            "HyperBit.hex from the same release ZIP as this PC agent. Otherwise a timeout on "
            "a BBC micro:bit candidate points at the BLE/runtime layer, not fluid rendering."
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
                self._mic_gap = True
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
            self._mic_gap = False
            self._cancel.clear()
            print("[device] gold logo down: microphone ON")

        elif code == EVT_PTT_END:
            samples = a | (b << 8) | ((c & 0x7F) << 16)
            overflow = bool(c & 0x80) or self._mic_gap
            utt = Utterance(bytes(self._recv), samples, overflow)
            self._loop.call_soon_threadsafe(self._utterances.put_nowait, utt)
            print(f"[device] gold logo up: microphone OFF; {len(self._recv)} ADPCM bytes")

        elif code == EVT_READY:
            self.firmware_revision = b
            self.capabilities = c
            if a != PROTOCOL_VERSION:
                self._ready_error = (
                    f"protocol mismatch: firmware={a}, pc={PROTOCOL_VERSION}"
                )
            elif b < MIN_FIRMWARE_REVISION:
                self._ready_error = (
                    f"stale HyperBit firmware revision {b}; this PC agent requires "
                    f"revision {MIN_FIRMWARE_REVISION}+"
                )
            elif (c & REQUIRED_CAPABILITIES) != REQUIRED_CAPABILITIES:
                self._ready_error = (
                    f"firmware r{b} is missing required capabilities "
                    f"0x{REQUIRED_CAPABILITIES:02x} (reported 0x{c:02x})"
                )
            else:
                self._ready_error = None
                print(
                    f"[device] firmware READY: protocol={a} revision={b} "
                    f"capabilities=0x{c:02x}"
                )
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

    async def _queue_or_disconnect(self, queue: asyncio.Queue):
        if self._disconnect_event.is_set():
            raise BLEDisconnectedError("HyperBit BLE session disconnected")

        item_task = asyncio.create_task(queue.get())
        disconnect_task = asyncio.create_task(self._disconnect_event.wait())
        done, pending = await asyncio.wait(
            {item_task, disconnect_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()

        if disconnect_task in done and disconnect_task.result():
            item_task.cancel()
            raise BLEDisconnectedError("HyperBit BLE session disconnected")
        return item_task.result()

    async def next_utterance(self):
        return await self._queue_or_disconnect(self._utterances)

    async def next_replay_request(self):
        await self._queue_or_disconnect(self._replay_requests)

    async def wait_disconnected(self):
        await self._disconnect_event.wait()

    def is_connected(self):
        return bool(self._session_active and self.client and self.client.is_connected)

    def cancelled(self):
        return self._cancel.is_set()

    def clear_cancel(self):
        self._cancel.clear()

    async def _write_control(
        self,
        code: int,
        a: int = 0,
        b: int = 0,
        c: int = 0,
        include_all: bool = False,
    ):
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

        ack_task = asyncio.create_task(self._tts_done.wait())
        disconnect_task = asyncio.create_task(self._disconnect_event.wait())
        try:
            done, pending = await asyncio.wait(
                {ack_task, disconnect_task},
                timeout=8.0,
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            if not done:
                try:
                    await self.abort_tts()
                except Exception:
                    pass
                raise RuntimeError("micro:bit did not acknowledge the TTS segment")
            if disconnect_task in done and disconnect_task.result():
                raise BLEDisconnectedError("HyperBit disconnected during TTS")
        finally:
            if not ack_task.done():
                ack_task.cancel()
            if not disconnect_task.done():
                disconnect_task.cancel()

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
        self._closing = True
        self._session_active = False
        client = self.client
        self.client = None
        self.tx_char = None
        self.rx_char = None
        if client:
            try:
                if client.is_connected:
                    await client.disconnect()
            except Exception:
                pass
