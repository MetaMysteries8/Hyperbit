from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class WinRTCompatTests(unittest.TestCase):
    def test_release_launcher_installs_compat_before_agent(self):
        launcher = (ROOT / "HyperBit.py").read_text(encoding="utf-8")
        install_at = launcher.index("winrt_ble_compat.install()")
        agent_at = launcher.index("runpy.run_path")
        self.assertLess(install_at, agent_at)

    def test_winrt_compat_targets_only_nus(self):
        source = (ROOT / "pc_agent" / "winrt_ble_compat.py").read_text(encoding="utf-8")
        self.assertIn('kwargs.setdefault("services", [ble_link.SERVICE_UUID])', source)
        self.assertIn("await asyncio.wait_for(client.disconnect(), timeout=5.0)", source)
        self.assertNotIn("if not client.is_connected", source)


if __name__ == "__main__":
    unittest.main()
