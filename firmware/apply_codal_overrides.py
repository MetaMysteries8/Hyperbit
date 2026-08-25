from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


MARKER = "HYPERBIT_CODAL_OVERRIDE"


def fail(message: str) -> None:
    raise SystemExit(f"HyperBit CODAL override failed: {message}")


def replace_exact_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        fail(f"expected exactly one {label} anchor, found {count}")
    return text.replace(old, new, 1)


def apply(samples_root: Path, config_path: Path) -> None:
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    target = samples_root / "libraries" / "codal-microbit-v2"
    manager = target / "source" / "bluetooth" / "MicroBitBLEManager.cpp"
    linker = target / "ld" / "nrf52833-softdevice.ld"

    if not manager.is_file() or not linker.is_file():
        fail(
            "CODAL target files are missing. Run CMake configure first so "
            "microbit-v2-samples fetches its locked dependencies."
        )

    actual_commit = subprocess.check_output(
        ["git", "-C", str(target), "rev-parse", "HEAD"], text=True
    ).strip()
    expected_commit = cfg["expected_codal_microbit_v2_commit"]
    if actual_commit != expected_commit:
        fail(
            f"codal-microbit-v2 is {actual_commit}, expected {expected_commit}; "
            "review the upstream changes before updating the override."
        )

    queue_size = int(cfg["hvn_tx_queue_size"])
    if not 2 <= queue_size <= 32:
        fail(f"hvn_tx_queue_size {queue_size} is outside the reviewed 2..32 range")

    app_origin = int(cfg["application_ram_origin"], 0)
    noinit_origin = int(cfg["noinit_origin"], 0)
    ram_end = int(cfg["ram_end"], 0)
    if noinit_origin + 0x10 != app_origin:
        fail("NOINIT must occupy exactly the 16 bytes immediately below application RAM")
    if not 0x20002040 < app_origin < ram_end:
        fail("application RAM origin is outside the expected nRF52833 RAM range")

    manager_text = manager.read_text(encoding="utf-8")
    override_block = f"""

    // {MARKER}: HyperBit streams 8 kHz IMA ADPCM over notifications. CODAL's
    // Nordic SDK defaults the server notification queue to one entry, which is
    // too shallow for bursty Windows connection events. Reserve a bounded queue
    // before enabling the SoftDevice; sendMic() still handles NRF_ERROR_RESOURCES
    // as normal backpressure when this queue is temporarily full.
    ble_cfg_t hyperbit_gatts_cfg;
    memset(&hyperbit_gatts_cfg, 0, sizeof(hyperbit_gatts_cfg));
    hyperbit_gatts_cfg.conn_cfg.conn_cfg_tag = microbit_ble_CONN_CFG_TAG;
    hyperbit_gatts_cfg.conn_cfg.params.gatts_conn_cfg.hvn_tx_queue_size = {queue_size};
    MICROBIT_BLE_ECHK(sd_ble_cfg_set(
        BLE_CONN_CFG_GATTS,
        &hyperbit_gatts_cfg,
        ram_start
    ));
"""

    if MARKER in manager_text:
        expected_line = (
            "hyperbit_gatts_cfg.conn_cfg.params.gatts_conn_cfg.hvn_tx_queue_size = "
            f"{queue_size};"
        )
        if manager_text.count(MARKER) != 1 or expected_line not in manager_text:
            fail("existing MicroBitBLEManager override does not match configuration")
    else:
        anchor = (
            "    MICROBIT_BLE_ECHK( nrf_sdh_ble_default_cfg_set( "
            "microbit_ble_CONN_CFG_TAG, &ram_start));\n"
        )
        manager_text = replace_exact_once(
            manager_text,
            anchor,
            anchor + override_block,
            "nrf_sdh_ble_default_cfg_set",
        )
        manager.write_text(manager_text, encoding="utf-8")

    linker_text = linker.read_text(encoding="utf-8")
    # Emit one canonical spelling so CI can prove the exact patched boundaries.
    wanted_noinit = (
        f"  NOINIT (rwx) : ORIGIN = 0X{noinit_origin:08X}, "
        f"LENGTH = 0X{app_origin:08X} - 0X{noinit_origin:08X}"
    )
    wanted_ram = (
        f"  RAM (rwx) : ORIGIN = 0X{app_origin:08X}, "
        f"LENGTH = 0X{ram_end:08X} - 0X{app_origin:08X}"
    )

    old_noinit = (
        "  NOINIT (rwx) : ORIGIN = 0x20002030, "
        "LENGTH = 0x20002040 - 0x20002030"
    )
    old_ram = (
        "  RAM (rwx) : ORIGIN = 0x20002040, "
        "LENGTH = 0x20020000 - 0x20002040"
    )

    if wanted_noinit not in linker_text:
        linker_text = replace_exact_once(
            linker_text, old_noinit, wanted_noinit, "SoftDevice NOINIT layout"
        )
    if wanted_ram not in linker_text:
        linker_text = replace_exact_once(
            linker_text, old_ram, wanted_ram, "SoftDevice application RAM layout"
        )
    linker.write_text(linker_text, encoding="utf-8")

    manager_final = manager.read_text(encoding="utf-8")
    linker_final = linker.read_text(encoding="utf-8")
    queue_line = (
        "hyperbit_gatts_cfg.conn_cfg.params.gatts_conn_cfg.hvn_tx_queue_size = "
        f"{queue_size};"
    )
    if manager_final.count(MARKER) != 1 or manager_final.count(queue_line) != 1:
        fail("notification queue override did not apply exactly once")
    if linker_final.count(wanted_noinit) != 1 or linker_final.count(wanted_ram) != 1:
        fail("reserved SoftDevice/application RAM layout did not apply exactly once")

    print(f"HyperBit CODAL override: codal={actual_commit}")
    print(f"HyperBit CODAL override: hvn_tx_queue_size={queue_size}")
    print(f"HyperBit CODAL override: noinit_origin=0X{noinit_origin:08X}")
    print(f"HyperBit CODAL override: application_ram_origin=0X{app_origin:08X}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply reviewed HyperBit BLE throughput overrides to a configured CODAL tree."
    )
    parser.add_argument("--samples-root", required=True, type=Path)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).with_name("codal_overrides.json"),
    )
    args = parser.parse_args()
    apply(args.samples_root.resolve(), args.config.resolve())


if __name__ == "__main__":
    main()
