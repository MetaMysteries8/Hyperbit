#!/usr/bin/env python3
"""Small release launcher for the HyperBit PC agent."""

from __future__ import annotations

from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parent
PC_AGENT = ROOT / "pc_agent"
ENTRYPOINT = PC_AGENT / "agent.py"

if not ENTRYPOINT.is_file():
    raise SystemExit("pc_agent/agent.py is missing. Extract the whole HyperBit release ZIP before running HyperBit.py.")

sys.path.insert(0, str(PC_AGENT))
runpy.run_path(str(ENTRYPOINT), run_name="__main__")
