from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class WinRTCompatTests(unittest.TestCase):
    def test_shared_agent_installs_compat_before_ble_import(self):
        agent = (ROOT / "pc_agent" / "agent.py").read_text(encoding="utf-8")
        install_at = agent.index("winrt_ble_compat.install()")
        ble_import_at = agent.index("from ble_link import")
        self.assertLess(install_at, ble_import_at)

    def test_release_launcher_routes_through_shared_agent(self):
        launcher = (ROOT / "HyperBit.py").read_text(encoding="utf-8")
        self.assertIn('runpy.run_path(str(ENTRYPOINT), run_name="__main__")', launcher)
        self.assertNotIn("winrt_ble_compat.install()", launcher)

    def test_winrt_compat_targets_only_nus(self):
        source = (ROOT / "pc_agent" / "winrt_ble_compat.py").read_text(encoding="utf-8")
        self.assertIn('kwargs.setdefault("services", [ble_link.SERVICE_UUID])', source)
        self.assertIn("await asyncio.wait_for(client.disconnect(), timeout=5.0)", source)
        self.assertNotIn("if not client.is_connected", source)


if __name__ == "__main__":
    unittest.main()
