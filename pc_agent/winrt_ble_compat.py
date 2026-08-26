from __future__ import annotations

import asyncio
import importlib.metadata
import inspect
import sys


def install() -> None:
    """Install HyperBit's Windows-only Bleak transport workarounds.

    WinRT service enumeration can spend the whole connection timeout walking a
    peripheral's complete GATT database. HyperBit knows the only application
    service it needs (Nordic UART Service), so on Windows request that UUID
    directly. Also make setup teardown close the Bleak/WinRT objects even when
    Bleak reports the GATT session as inactive; an inactive GattSession is not
    proof that Windows has released the underlying peripheral link.
    """
    if sys.platform != "win32":
        return

    import ble_link
    from bleak import BleakClient as NativeBleakClient

    if getattr(ble_link, "_hyperbit_winrt_compat_installed", False):
        return

    parameters = inspect.signature(NativeBleakClient).parameters
    supports_service_filter = "services" in parameters

    if supports_service_filter:
        class HyperBitWinRTClient(NativeBleakClient):
            def __init__(self, address_or_ble_device, *args, **kwargs):
                kwargs.setdefault("services", [ble_link.SERVICE_UUID])
                super().__init__(address_or_ble_device, *args, **kwargs)

        ble_link.BleakClient = HyperBitWinRTClient

    async def disconnect_partial(self) -> bool:
        self._session_active = False
        client = self.client
        self.client = None
        self.tx_char = None
        self.rx_char = None
        self._ready.clear()
        if client is None:
            return False

        # Always ask Bleak to dispose the WinRT GattSession/requester. The old
        # path skipped disconnect() whenever is_connected was already false,
        # which is exactly the ambiguous state produced by failed discovery.
        was_connected = bool(client.is_connected)
        try:
            await asyncio.wait_for(client.disconnect(), timeout=5.0)
            return was_connected and not client.is_connected
        except Exception as exc:
            print(f"[ble] partial WinRT cleanup did not complete: {type(exc).__name__}")
            return False

    ble_link.HyperBitBLE._disconnect_partial = disconnect_partial
    ble_link._hyperbit_winrt_compat_installed = True

    try:
        bleak_version = importlib.metadata.version("bleak")
    except importlib.metadata.PackageNotFoundError:
        bleak_version = "unknown"

    if supports_service_filter:
        print(
            f"[ble] Windows transport: Bleak {bleak_version}; "
            "NUS-only GATT discovery enabled"
        )
    else:
        print(
            f"[ble] Windows transport: Bleak {bleak_version}; this Bleak version "
            "does not expose service filtering, using full GATT discovery"
        )
