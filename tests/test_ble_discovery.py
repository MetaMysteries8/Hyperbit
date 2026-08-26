import asyncio
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
PC_AGENT = ROOT / "pc_agent"
if str(PC_AGENT) not in sys.path:
    sys.path.insert(0, str(PC_AGENT))


class _ScannerStub:
    found = {}

    @classmethod
    async def discover(cls, timeout=10.0, return_adv=False):
        return cls.found


class _ClientStub:
    pass


fake_bleak = types.ModuleType("bleak")
fake_bleak.BleakScanner = _ScannerStub
fake_bleak.BleakClient = _ClientStub
sys.modules.setdefault("bleak", fake_bleak)

import ble_link  # noqa: E402


class _Device:
    def __init__(self, address: str, name=None):
        self.address = address
        self.name = name


class _Adv:
    def __init__(self, local_name=None, service_uuids=None):
        self.local_name = local_name
        self.service_uuids = service_uuids or []


class DiscoveryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        _ScannerStub.found = {}

    async def test_advertised_microbit_name_survives_blank_bledevice_name(self):
        dev = _Device("AA:BB:CC:DD:EE:01", name=None)
        adv = _Adv(local_name="BBC micro:bit [test]", service_uuids=[])
        _ScannerStub.found = {"one": (dev, adv)}

        transport = ble_link.HyperBitBLE()
        candidates = await transport._find_candidates()

        self.assertEqual(len(candidates), 1)
        self.assertTrue(candidates[0].is_microbit)
        self.assertEqual(candidates[0].display_name, "BBC micro:bit [test]")
        self.assertIs(candidates[0].device, dev)

    async def test_generic_nus_is_kept_but_not_misclassified(self):
        dev = _Device("AA:BB:CC:DD:EE:02", name="sensor")
        adv = _Adv(local_name="sensor", service_uuids=[ble_link.SERVICE_UUID])
        _ScannerStub.found = {"one": (dev, adv)}

        transport = ble_link.HyperBitBLE()
        candidates = await transport._find_candidates()

        self.assertEqual(len(candidates), 1)
        self.assertFalse(candidates[0].is_microbit)

    async def test_recovery_rescan_reacquires_fresh_device_by_address(self):
        old_dev = _Device("AA:BB:CC:DD:EE:03", name="BBC micro:bit [test]")
        new_dev = _Device("AA:BB:CC:DD:EE:03", name=None)
        adv = _Adv(local_name="BBC micro:bit [test]", service_uuids=[])
        _ScannerStub.found = {"fresh": (new_dev, adv)}

        transport = ble_link.HyperBitBLE()
        original = ble_link.Candidate(old_dev, "BBC micro:bit [test]", True)
        refreshed = await transport._refresh_candidate(original)

        self.assertIs(refreshed.device, new_dev)
        self.assertEqual(refreshed.display_name, "BBC micro:bit [test]")
        self.assertTrue(refreshed.is_microbit)

    async def test_recovery_rescan_keeps_old_object_if_board_is_missing(self):
        old_dev = _Device("AA:BB:CC:DD:EE:04", name="BBC micro:bit [test]")
        _ScannerStub.found = {}

        transport = ble_link.HyperBitBLE()
        original = ble_link.Candidate(old_dev, "BBC micro:bit [test]", True)
        refreshed = await transport._refresh_candidate(original)

        self.assertIs(refreshed, original)

    async def test_stale_firmware_ready_is_rejected_immediately(self):
        transport = ble_link.HyperBitBLE()
        transport._loop = asyncio.get_running_loop()
        stale = bytearray([
            ble_link.FRAME_CONTROL,
            ble_link.EVT_READY,
            ble_link.PROTOCOL_VERSION,
            ble_link.MIN_FIRMWARE_REVISION - 1,
            ble_link.REQUIRED_CAPABILITIES,
        ])
        transport._nus_notify(None, stale)
        await asyncio.sleep(0)

        self.assertTrue(transport._ready.is_set())
        self.assertIsNotNone(transport._ready_error)
        self.assertIn("stale HyperBit firmware", transport._ready_error)

    async def test_current_ready_records_revision_and_capabilities(self):
        transport = ble_link.HyperBitBLE()
        transport._loop = asyncio.get_running_loop()
        caps = ble_link.REQUIRED_CAPABILITIES | ble_link.CAP_SAFE_RAINBOW_PWM
        ready = bytearray([
            ble_link.FRAME_CONTROL,
            ble_link.EVT_READY,
            ble_link.PROTOCOL_VERSION,
            ble_link.MIN_FIRMWARE_REVISION,
            caps,
        ])
        transport._nus_notify(None, ready)
        await asyncio.sleep(0)

        self.assertTrue(transport._ready.is_set())
        self.assertIsNone(transport._ready_error)
        self.assertEqual(transport.firmware_revision, ble_link.MIN_FIRMWARE_REVISION)
        self.assertEqual(transport.capabilities, caps)

    async def test_superseded_disconnect_callback_cannot_kill_current_session(self):
        transport = ble_link.HyperBitBLE()
        transport._loop = asyncio.get_running_loop()
        old_client = object()
        current_client = object()
        transport.client = current_client
        transport._session_active = True

        transport._on_disconnected(old_client)
        await asyncio.sleep(0)

        self.assertTrue(transport._session_active)
        self.assertFalse(transport._disconnect_event.is_set())
        self.assertFalse(transport._cancel.is_set())

        transport._on_disconnected(current_client)
        await asyncio.sleep(0)

        self.assertFalse(transport._session_active)
        self.assertTrue(transport._disconnect_event.is_set())
        self.assertTrue(transport._cancel.is_set())

    def test_retry_logic_uses_preserved_candidate_classification(self):
        source = (PC_AGENT / "ble_link.py").read_text(encoding="utf-8")
        self.assertIn("current_candidate.is_microbit", source)
        self.assertNotIn("looks_like_microbit = self._looks_like_microbit(dev.name", source)
        self.assertIn("current_candidate = await self._refresh_candidate(current_candidate)", source)


if __name__ == "__main__":
    unittest.main()
