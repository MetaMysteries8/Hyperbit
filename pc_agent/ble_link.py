from __future__ import annotations
import asyncio
from dataclasses import dataclass
from bleak import BleakClient, BleakScanner

SERVICE_UUID = "7f9a0001-4c1d-4b8f-9a31-c62d5e8b1f70"
MIC_UUID     = "7f9a0002-4c1d-4b8f-9a31-c62d5e8b1f70"
SPEAKER_UUID = "7f9a0003-4c1d-4b8f-9a31-c62d5e8b1f70"
CONTROL_UUID = "7f9a0004-4c1d-4b8f-9a31-c62d5e8b1f70"

EVT_PTT_START = 0x10
EVT_PTT_END   = 0x11
EVT_READY     = 0x12

CMD_TTS_START = 0x30
CMD_TTS_END   = 0x31
CMD_SET_STATE = 0x40

STATE_IDLE = 1
STATE_LISTENING = 2
STATE_TRANSCRIBING = 3
STATE_THINKING = 4
STATE_SPEAKING = 5
STATE_ERROR = 6


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
        self._loop = None

    async def _find(self):
        print("[ble] scanning 10 seconds...")
        found = await BleakScanner.discover(timeout=10.0, return_adv=True)
        candidates = []
        seen = []

        for _k, pair in found.items():
            device, adv = pair
            name = adv.local_name or device.name or ""
            service_uuids = [u.lower() for u in (adv.service_uuids or [])]
            seen.append((name or "<unnamed>", device.address, service_uuids))

            if self.address and device.address.lower() == self.address.lower():
                print(f"[ble] matched requested address: {device.address}")
                return device

            if self.name_hint and self.name_hint.lower() in name.lower():
                candidates.append(device)
                continue

            if SERVICE_UUID.lower() in service_uuids:
                print(f"[ble] matched advertised HyperBit service on {device.address}")
                candidates.append(device)
                continue

            if not self.name_hint and ("micro:bit" in name.lower() or "microbit" in name.lower()):
                candidates.append(device)

        if not candidates:
            print("[ble] no HyperBit candidate matched. Devices seen by Windows:")
            if not seen:
                print("  (none)")
            for name, address, service_uuids in seen[:40]:
                services = ", ".join(service_uuids) if service_uuids else "<no advertised services>"
                print(f"  {name}  {address}  services={services}")
            raise RuntimeError(
                "No advertising HyperBit/micro:bit found. If the board appears in the list above but does not advertise the HyperBit service, the firmware advertising needs fixing."
            )

        device = candidates[0]
        print(f"[ble] selected {device.name or 'micro:bit'} ({device.address})")
        return device

    async def connect(self):
        dev = await self._find()
        print(f"[ble] connecting to {dev.name or 'micro:bit'} ({dev.address})")
        self.client = BleakClient(dev, timeout=20.0)
        await self.client.connect()
        svc = self.client.services.get_service(SERVICE_UUID)
        if svc is None:
            print("[ble] services present on connected device:")
            for s in self.client.services:
                print(" ", s.uuid)
            raise RuntimeError("HyperBit BLE service is missing; the board was found, but this firmware does not expose the expected service.")
        self.mic_char = svc.get_characteristic(MIC_UUID)
        self.speaker_char = svc.get_characteristic(SPEAKER_UUID)
        self.control_char = svc.get_characteristic(CONTROL_UUID)
        if not all((self.mic_char, self.speaker_char, self.control_char)):
            raise RuntimeError("HyperBit service is missing one or more characteristics.")

        self._loop = asyncio.get_running_loop()
        await self.client.start_notify(self.mic_char, self._mic_notify)
        await self.client.start_notify(self.control_char, self._control_notify)
        print("[ble] connected; notifications armed")
        await self.set_state(STATE_IDLE)

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
            print("[device] PTT down")
        elif code == EVT_PTT_END:
            samples = 0
            overflow = False
            if len(data) >= 3:
                samples = data[1] | (data[2] << 8)
            if len(data) >= 4:
                overflow = bool(data[3])
            utt = Utterance(bytes(self._recv), samples, overflow)
            self._loop.call_soon_threadsafe(self._utterances.put_nowait, utt)
            print(f"[device] PTT up; {len(self._recv)} ADPCM bytes, {samples} samples")
        elif code == EVT_READY:
            print("[device] firmware ready")

    async def next_utterance(self):
        return await self._utterances.get()

    async def _write_control(self, payload: bytes):
        assert self.client and self.control_char
        props = {p.lower() for p in self.control_char.properties}
        response = "write-without-response" not in props
        await self.client.write_gatt_char(self.control_char, payload, response=response)

    async def set_state(self, state: int):
        await self._write_control(bytes([CMD_SET_STATE, state & 0xFF]))

    async def send_tts(self, adpcm: bytes):
        assert self.client and self.speaker_char
        if len(adpcm) > 20000:
            adpcm = adpcm[:20000]
        await self._write_control(bytes([CMD_TTS_START, len(adpcm) & 0xFF, (len(adpcm) >> 8) & 0xFF]))

        props = {p.lower() for p in self.speaker_char.properties}
        response = "write-without-response" not in props
        seq = 0
        for off in range(0, len(adpcm), 19):
            packet = bytes([seq]) + adpcm[off:off+19]
            await self.client.write_gatt_char(self.speaker_char, packet, response=response)
            seq = (seq + 1) & 0xFF
            await asyncio.sleep(0.003)

        await self._write_control(bytes([CMD_TTS_END]))

    async def close(self):
        if self.client:
            try:
                if self.client.is_connected:
                    await self.client.disconnect()
            finally:
                self.client = None
