from pathlib import Path
import json
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CFG_PATH = ROOT / "firmware" / "codal_overrides.json"
SCRIPT_PATH = ROOT / "firmware" / "apply_codal_overrides.py"
HEADER_PATH = ROOT / "firmware" / "source" / "VoiceBLEService.h"
PC_PATH = ROOT / "pc_agent" / "ble_link.py"

CFG = json.loads(CFG_PATH.read_text(encoding="utf-8"))
SCRIPT = SCRIPT_PATH.read_text(encoding="utf-8")
HEADER = HEADER_PATH.read_text(encoding="utf-8")
PC = PC_PATH.read_text(encoding="utf-8")


class CodalOverrideTests(unittest.TestCase):
    def test_notification_queue_has_reviewed_headroom(self):
        queue = int(CFG["hvn_tx_queue_size"])
        self.assertGreaterEqual(queue, 12)
        self.assertLessEqual(queue, 32)

        # 8 kHz IMA ADPCM is 4,000 bytes/s. With 17 audio bytes per
        # notification, HyperBit needs about 236 notifications/s while talking.
        required_notifications_per_second = 4000 / 17
        preferred_max_interval_seconds = 0.020
        queue_capacity_at_20ms = queue / preferred_max_interval_seconds
        self.assertGreater(queue_capacity_at_20ms, required_notifications_per_second * 2)

    def test_application_ram_reservation_is_conservative(self):
        app_origin = int(CFG["application_ram_origin"], 0)
        noinit_origin = int(CFG["noinit_origin"], 0)
        ram_end = int(CFG["ram_end"], 0)
        self.assertEqual(app_origin, 0x20006000)
        self.assertEqual(noinit_origin + 0x10, app_origin)
        self.assertGreater(ram_end - app_origin, 96 * 1024)

    def test_override_is_fail_closed_and_configures_gatts_queue(self):
        self.assertIn("expected_codal_microbit_v2_commit", SCRIPT)
        self.assertIn("BLE_CONN_CFG_GATTS", SCRIPT)
        self.assertIn("hvn_tx_queue_size", SCRIPT)
        self.assertIn("expected exactly one", SCRIPT)
        self.assertIn("review the upstream changes", SCRIPT)

    def test_firmware_and_pc_require_buffered_hvn_capability(self):
        self.assertRegex(
            HEADER,
            r"#define\s+HYPERBIT_CAP_BUFFERED_HVN\s+0x08",
        )
        self.assertIsNotNone(
            re.search(r"^CAP_BUFFERED_HVN\s*=\s*0x08\s*$", PC, re.M)
        )

        # REQUIRED_CAPABILITIES is intentionally formatted over several lines.
        # Parse the complete assignment block rather than assuming a one-line RHS.
        required_start = PC.index("REQUIRED_CAPABILITIES =")
        required_end = PC.index("AUDIO_PAYLOAD_BYTES", required_start)
        required_block = PC[required_start:required_end]
        self.assertIn("CAP_BUFFERED_HVN", required_block)
        self.assertIn("CAP_BOUNDED_LINK_RECOVERY", required_block)


if __name__ == "__main__":
    unittest.main()
