from pathlib import Path
import json
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
HEADER = (ROOT / "firmware/source/VoiceBLEService.h").read_text(encoding="utf-8")
SERVICE = (ROOT / "firmware/source/VoiceBLEService.cpp").read_text(encoding="utf-8")
MAIN = (ROOT / "firmware/source/main.cpp").read_text(encoding="utf-8")
ANIMATOR = (ROOT / "firmware/source/AliveAnimator.cpp").read_text(encoding="utf-8")
RAINBOW = (ROOT / "firmware/source/WukongRainbow.cpp").read_text(encoding="utf-8")
PC = (ROOT / "pc_agent/ble_link.py").read_text(encoding="utf-8")
CODAL = json.loads((ROOT / "firmware/codal.json").read_text(encoding="utf-8"))


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
            ("HYPERBIT_CAP_BUFFERED_HVN", "CAP_BUFFERED_HVN"),
            ("HYPERBIT_CAP_BOUNDED_LINK_RECOVERY", "CAP_BOUNDED_LINK_RECOVERY"),
        ]
        for firmware_name, pc_name in pairs:
            with self.subTest(firmware=firmware_name, pc=pc_name):
                self.assertEqual(cpp_int(firmware_name), py_int(pc_name))

    def test_codal_uart_gatt_capability_is_advertised(self):
        self.assertEqual(cpp_int("HYPERBIT_CAP_CODAL_UART_GATT"), 0x20)
        capabilities_line = next(
            line for line in HEADER.splitlines()
            if line.startswith("#define HYPERBIT_CAPABILITIES")
        )
        self.assertIn("HYPERBIT_CAP_CODAL_UART_GATT", capabilities_line)

    def test_nus_uuid_contract_is_standard_and_owned_by_codal_uart(self):
        self.assertIn('SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"', PC)
        self.assertIn('RX_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"', PC)
        self.assertIn('TX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"', PC)

        self.assertIn("class VoiceBLEService : public codal::MicroBitUARTService", HEADER)
        self.assertIn("MicroBitUARTService(*MicroBitBLEManager::getInstance())", SERVICE)
        self.assertIn("(int)HB_NUS_TX == (int)MicroBitUARTService::mbbs_cIdxTX", SERVICE)
        self.assertIn("(int)HB_NUS_RX == (int)MicroBitUARTService::mbbs_cIdxRX", SERVICE)
        self.assertIn("(int)HB_CHAR_COUNT == (int)MicroBitUARTService::mbbs_cIdxCOUNT", SERVICE)
        self.assertNotRegex(SERVICE, r"(?m)^\s*RegisterBaseUUID\(")
        self.assertNotRegex(SERVICE, r"(?m)^\s*CreateService\(")
        self.assertNotRegex(SERVICE, r"(?m)^\s*CreateCharacteristic\(")
        self.assertEqual(CODAL["config"].get("MICROBIT_BLE_NORDIC_STYLE_UART"), 1)

    def test_hello_requires_tx_subscription(self):
        hello_start = SERVICE.index("if (frameType == HB_FRAME_HELLO)")
        hello_end = SERVICE.index("// Ignore application data", hello_start)
        hello_block = SERVICE[hello_start:hello_end]
        self.assertIn("notifyChrValueEnabled(HB_NUS_TX)", hello_block)

    def test_ble_lifecycle_resets_session_immediately(self):
        self.assertIn("VoiceBLEService::onConnect", SERVICE)
        self.assertIn("VoiceBLEService::onDisconnect", SERVICE)
        self.assertGreaterEqual(SERVICE.count("resetSession();"), 2)

    def test_ready_reports_revision_and_capabilities_before_application_resume(self):
        ready = MAIN.index("HB_EVT_READY")
        application_ready = MAIN.index("applicationReady = true;", ready)
        self.assertLess(ready, application_ready)
        ready_window = MAIN[ready:application_ready]
        self.assertIn("HYPERBIT_FIRMWARE_REVISION", ready_window)
        self.assertIn("HYPERBIT_CAPABILITIES", ready_window)

    def test_connection_freezes_animation_without_disabling_matrix_driver(self):
        # CODAL's V2 BLE sample supports the LED matrix while connected. r5 keeps
        # TIMER4/display lifecycle stable and simply stops scheduling animator ticks.
        self.assertNotIn("uBit.display.disable()", MAIN)
        self.assertNotIn("uBit.display.enable()", MAIN)
        self.assertIn("animator.setState(PHYS_CONNECTING);", MAIN)
        self.assertIn("if (!rawConnected)", MAIN)
        self.assertIn("animator.tick();", MAIN)

    def test_half_open_ble_recovery_is_bounded_and_hard_fails_safe(self):
        self.assertIn("HALF_OPEN_LIMIT_TICKS = 3800", MAIN)
        self.assertIn("DISCONNECT_GRACE_TICKS = 200", MAIN)

        # Runtime order spans multiple loop iterations: first the half-open timer
        # requests a disconnect and sets recoveryDisconnectPending; on later
        # iterations the pending branch counts its grace window and resets only if
        # the SoftDevice still reports the raw link. Validate those two states
        # independently instead of incorrectly requiring their source-text order.
        handshake_start = MAIN.index("if (rawConnected && !applicationReady)")
        handshake_end = MAIN.index("if (!applicationReady)", handshake_start)
        handshake = MAIN[handshake_start:handshake_end]

        pending_start = handshake.index("if (recoveryDisconnectPending)")
        half_open_start = handshake.index("if (++halfOpenTicks >= HALF_OPEN_LIMIT_TICKS)")
        pending_block = handshake[pending_start:half_open_start]
        half_open_block = handshake[half_open_start:]

        self.assertIn("++disconnectGraceTicks >= DISCONNECT_GRACE_TICKS", pending_block)
        self.assertIn("target_reset();", pending_block)
        self.assertIn("disconnectCurrentConnection(voice);", half_open_block)
        self.assertIn("recoveryDisconnectPending = true;", half_open_block)
        self.assertIn("disconnectGraceTicks = 0;", half_open_block)

    def test_idle_animation_is_specs_aware(self):
        # 25 Hz instead of ~33 Hz, and accelerometer reads only feed fluid states.
        self.assertGreaterEqual(MAIN.count("animationDivider >= 4"), 2)
        tick = ANIMATOR.index("void AliveAnimator::tick()")
        accel = ANIMATOR.index("bit.accelerometer.getX()", tick)
        fluid_guard = ANIMATOR.rfind("stateValue == PHYS_DISCONNECTED || stateValue == PHYS_IDLE", tick, accel)
        self.assertNotEqual(fluid_guard, -1)

    def test_critical_controls_use_bounded_notification_backpressure(self):
        helper_start = MAIN.index("static bool sendCriticalControl")
        helper_end = MAIN.index("static void drainMicPackets", helper_start)
        helper = MAIN[helper_start:helper_end]
        self.assertIn("MAX_TRIES = 250", helper)
        self.assertIn("uBit.sleep(2)", helper)
        self.assertIn("disconnectCurrentConnection(ble)", helper)

        # Critical controls may be emitted from main() (where the service object
        # is named `voice`) or a helper such as finishMicUtterance() (where it is
        # named `ble`). Verify they route through sendCriticalControl regardless
        # of the local identifier rather than matching one spelling literally.
        for event in (
            "HB_EVT_PTT_START",
            "HB_EVT_PTT_END",
            "HB_EVT_TTS_SEGMENT_DONE",
            "HB_EVT_CANCEL",
            "HB_EVT_REPLAY",
            "HB_EVT_MUTE_CHANGED",
        ):
            with self.subTest(event=event):
                self.assertRegex(
                    MAIN,
                    rf"sendCriticalControl\([^,]+,\s*{event}(?:\s*[,\)])",
                )

        # The PC must learn the utterance boundary before capture can produce its
        # first audio packet, and release must be sent only after final drain.
        ptt_start = MAIN.index("sendCriticalControl(voice, HB_EVT_PTT_START)")
        mic_activate = MAIN.index("uBit.audio.activateMic();", ptt_start)
        self.assertLess(ptt_start, mic_activate)

        finish_start = MAIN.index("static bool finishMicUtterance")
        finish_end = MAIN.index("static uint8_t visualStateFromPc", finish_start)
        finish = MAIN[finish_start:finish_end]
        self.assertLess(finish.index("drainMicPackets"), finish.index("HB_EVT_PTT_END"))

    def test_rainbow_driver_never_masks_interrupts(self):
        forbidden = ("__disable_irq", "target_disable_irq", "target_enable_irq")
        for token in forbidden:
            self.assertNotIn(token, RAINBOW)
        self.assertIn("neopixel_send_buffer", RAINBOW)


if __name__ == "__main__":
    unittest.main()
