from __future__ import annotations

import argparse
import asyncio
import inspect
from importlib.metadata import version as package_version

from bleak import BleakClient, BleakScanner

NUS_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"


def is_microbit(device, advertisement_data) -> bool:
    names = [
        getattr(device, "name", "") or "",
        getattr(advertisement_data, "local_name", "") or "",
    ]
    return any("micro:bit" in name.lower() for name in names)


async def main(pair: bool) -> int:
    print(f"[diag] Bleak {package_version('bleak')}")
    print(f"[diag] mode: {'pairing' if pair else 'open-link'}")
    print("[diag] scanning 10 seconds...")

    discovered = await BleakScanner.discover(timeout=10.0, return_adv=True)
    candidates = []
    for _address, (device, adv) in discovered.items():
        if is_microbit(device, adv):
            candidates.append((device, adv))

    if not candidates:
        print("[diag] FAIL: no BBC micro:bit advertisement found")
        return 2

    for idx, (device, adv) in enumerate(candidates, 1):
        name = getattr(device, "name", None) or getattr(adv, "local_name", None) or "(unnamed)"
        print(f"  [{idx}] {name} ({device.address})")

    device, adv = candidates[0]
    name = getattr(device, "name", None) or getattr(adv, "local_name", None) or "(unnamed)"
    print(f"[diag] connecting to {name} ({device.address})")

    kwargs = {"timeout": 40.0}
    try:
        parameters = inspect.signature(BleakClient).parameters
    except (TypeError, ValueError):
        parameters = {}

    # Target only NUS when supported so Windows does not need to enumerate every
    # unrelated service before this diagnostic can answer the question we care about.
    if "services" in parameters:
        kwargs["services"] = [NUS_SERVICE_UUID]
        print("[diag] NUS-only WinRT service discovery enabled")
    if pair and "pair" in parameters:
        kwargs["pair"] = True
        print("[diag] Windows pairing requested before service discovery")

    client = BleakClient(device, **kwargs)
    try:
        await client.connect()
        print(f"[diag] LINK CONNECTED: {client.is_connected}")

        services = client.services
        found_nus = False
        print("[diag] GATT services returned by Windows:")
        for service in services:
            print(f"  service {service.uuid}")
            if service.uuid.lower() == NUS_SERVICE_UUID:
                found_nus = True
            for char in service.characteristics:
                properties = ",".join(char.properties)
                print(f"    char {char.uuid} [{properties}]")

        if found_nus:
            print("[diag] PASS: Windows reached the stock CODAL Nordic UART Service.")
            return 0

        print("[diag] PARTIAL PASS: Windows completed GATT discovery, but NUS was not returned.")
        return 3
    except Exception as exc:
        print(f"[diag] FAIL during connect/GATT discovery: {type(exc).__name__}: {exc}")
        raise
    finally:
        try:
            await asyncio.wait_for(client.disconnect(), timeout=5.0)
        except Exception as exc:
            print(f"[diag] cleanup warning: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Test raw Windows GATT discovery against stock CODAL MicroBitUARTService."
    )
    parser.add_argument(
        "--pair",
        action="store_true",
        help="Request Windows pairing; use with CODAL-UART-PAIRING.hex.",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.pair)))
