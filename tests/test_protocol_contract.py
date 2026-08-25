from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
HEADER = (ROOT / "firmware/source/VoiceBLEService.h").read_text(encoding="utf-8")
SERVICE = (ROOT / "firmware/source/VoiceBLEService.cpp").read_text(encoding="utf-8")
MAIN = (ROOT / "firmware/source/main.cpp").read_text(encoding="utf-8")
RAINBOW = (ROOT / "firmware/source/WukongRainbow.cpp").read_text(encoding="utf-8")
PC = (ROOT / "pc_agent/ble_link.py").read_text(encoding="utf-8")


def cpp_int(name: str) -> int:
    match = re.search(rf"^#define\s+{re.escape(name)}\s+(0x[0-9a-fA-F]+|\d+)\s*$", HEADER, re.M)
    if not match:
        raise AssertionError(f"missing numeric firmware macro {name}")
    return int(match.group(1), 0)


def py_int(name: str) -> int:
    match = re.search(rf"^{re.escape(name)}\s*=\s*(0x[0-9a-fA-F]+|\d+)\s*$", PC, re.M)
    if not match:
        raise AssertionError(f"missing numeric PC constant {name}")
    return int(match.group(1), 0)


class ProtocolContractTests(unittest.TestCase):
    def test_wire_size_constants_match(self):
        self.assertEqual(cpp_int("HYPERBIT_PROTOCOL_VERSION"), py_int("PROTOCOL_VERSION"))
        self.assertEqual(cpp_int("HYPERBIT_FIRMWARE_REVISION"), py_int("MIN_FIRMWARE_REVISION"))
        self.assertEqual(cpp_int("HYPERBIT_NUS_AUDIO_PAYLOAD"), py_int("AUDIO_PAYLOAD_BYTES"))
        self.assertEqual(cpp_int("HYPERBIT_MAX_TTS_ADPCM"), py_int("TTS_SEGMENT_BYTES"))

    def test_capability_bits_match(self):
        pairs = [
            ("HYPERBIT_CAP_CONNECTION_ISOLATION", "CAP_CONNECTION_ISOLATION"),
            ("HYPERBIT_CAP_SAFE_RAINBOW_PWM", "CAP_SAFE_RAINBOW_PWM"),
            ("HYPERBIT_CAP_SEGMENTED_TTS", "CAP_SEGMENTED_TTS"),
        ]
        for firmware_name, pc_name in pairs:
            with self.subTest(firmware=firmware_name, pc=pc_name):
                self.assertEqual(cpp_int(firmware_name), py_int(pc_name))

    def test_nus_uuid_contract_is_standard(self):
        self.assertIn('SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"', PC)
        self.assertIn('RX_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"', PC)
        self.assertIn('TX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"', PC)
        self.assertIn("static const uint16_t NUS_SERVICE_UUID = 0x0001;", SERVICE)
        self.assertIn("static const uint16_t NUS_RX_UUID = 0x0002;", SERVICE)
        self.assertIn("static const uint16_t NUS_TX_UUID = 0x0003;", SERVICE)

    def test_hello_requires_tx_subscription(self):
        hello_start = SERVICE.index("if (frameType == HB_FRAME_HELLO)")
        hello_end = SERVICE.index("// Ignore application data", hello_start)
        hello_block = SERVICE[hello_start:hello_end]
        self.assertIn("notifyChrValueEnabled(HB_NUS_TX)", hello_block)

    def test_ble_lifecycle_resets_session_immediately(self):
        self.assertIn("VoiceBLEService::onConnect", SERVICE)
        self.assertIn("VoiceBLEService::onDisconnect", SERVICE)
        self.assertGreaterEqual(SERVICE.count("resetSession();"), 2)

    def test_ready_reports_revision_and_capabilities_before_resume(self):
        ready = MAIN.index("HB_EVT_READY")
        resume = MAIN.index("resumeDisplayAfterConnection(displaySuspended);", ready)
        self.assertLess(ready, resume)
        ready_window = MAIN[ready:resume]
        self.assertIn("HYPERBIT_FIRMWARE_REVISION", ready_window)
        self.assertIn("HYPERBIT_CAPABILITIES", ready_window)

    def test_rainbow_driver_never_masks_interrupts(self):
        forbidden = ("__disable_irq", "target_disable_irq", "target_enable_irq")
        for token in forbidden:
            self.assertNotIn(token, RAINBOW)
        self.assertIn("neopixel_send_buffer", RAINBOW)


if __name__ == "__main__":
    unittest.main()
