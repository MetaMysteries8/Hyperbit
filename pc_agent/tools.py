from __future__ import annotations
from pathlib import Path
from datetime import datetime
import json
import platform
import psutil


class AgentHome:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.workspace = (self.root / "workspace").resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.mem_path = self.root / "memory.json"
        if not self.mem_path.exists():
            self.mem_path.write_text("{}", encoding="utf-8")

    def _safe(self, rel: str) -> Path:
        p = (self.workspace / rel).resolve()
        if p != self.workspace and self.workspace not in p.parents:
            raise ValueError("Path escapes the agent workspace")
        return p

    def remember(self, key: str, value: str):
        data = json.loads(self.mem_path.read_text(encoding="utf-8"))
        data[key] = value
        self.mem_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return {"ok": True, "key": key}

    def recall(self, key: str):
        data = json.loads(self.mem_path.read_text(encoding="utf-8"))
        return {"key": key, "value": data.get(key)}

    def list_memories(self):
        return json.loads(self.mem_path.read_text(encoding="utf-8"))

    def list_workspace(self, path: str = "."):
        p = self._safe(path)
        if not p.exists():
            return {"error": "path does not exist"}
        if p.is_file():
            return [{"name": p.name, "type": "file", "bytes": p.stat().st_size}]
        return [{"name": x.name, "type": "dir" if x.is_dir() else "file", "bytes": None if x.is_dir() else x.stat().st_size} for x in sorted(p.iterdir(), key=lambda v: (not v.is_dir(), v.name.lower()))][:100]

    def read_text_file(self, path: str):
        p = self._safe(path)
        if not p.is_file():
            return {"error": "not a file"}
        text = p.read_text(encoding="utf-8", errors="replace")
        return {"path": path, "text": text[:20000], "truncated": len(text) > 20000}

    def write_text_file(self, path: str, text: str):
        p = self._safe(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return {"ok": True, "path": path, "bytes": len(text.encode("utf-8"))}


TOOL_DEFS = [
    {"type": "function", "function": {"name": "get_time", "description": "Get the PC's current local date and time.", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}},
    {"type": "function", "function": {"name": "pc_status", "description": "Get basic non-sensitive PC health information: OS, CPU load, RAM use, and battery if present.", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}},
    {"type": "function", "function": {"name": "remember", "description": "Store a small durable memory in the agent's own home.", "parameters": {"type": "object", "properties": {"key": {"type": "string"}, "value": {"type": "string"}}, "required": ["key", "value"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "recall", "description": "Recall one durable memory by key.", "parameters": {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "list_memories", "description": "List all small durable memories stored by the agent.", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}},
    {"type": "function", "function": {"name": "list_workspace", "description": "List files inside the agent's sandboxed workspace.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "default": "."}}, "additionalProperties": False}}},
    {"type": "function", "function": {"name": "read_text_file", "description": "Read a UTF-8 text file inside the agent's sandboxed workspace.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "write_text_file", "description": "Create or replace a UTF-8 text file inside the agent's sandboxed workspace.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "text": {"type": "string"}}, "required": ["path", "text"], "additionalProperties": False}}}
]


def execute_tool(home: AgentHome, name: str, args: dict):
    if name == "get_time":
        return {"local_time": datetime.now().astimezone().isoformat()}
    if name == "pc_status":
        battery = psutil.sensors_battery()
        vm = psutil.virtual_memory()
        return {"os": platform.platform(), "cpu_percent": psutil.cpu_percent(interval=0.15), "ram_percent": vm.percent, "ram_available_gb": round(vm.available / (1024**3), 2), "battery": None if battery is None else {"percent": battery.percent, "plugged_in": battery.power_plugged}}
    if name == "remember":
        return home.remember(args["key"], args["value"])
    if name == "recall":
        return home.recall(args["key"])
    if name == "list_memories":
        return home.list_memories()
    if name == "list_workspace":
        return home.list_workspace(args.get("path", "."))
    if name == "read_text_file":
        return home.read_text_file(args["path"])
    if name == "write_text_file":
        return home.write_text_file(args["path"], args["text"])
    return {"error": f"unknown tool: {name}"}
