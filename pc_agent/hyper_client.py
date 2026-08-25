from __future__ import annotations
from pathlib import Path
import json
import os
import httpx

from tools import AgentHome, TOOL_DEFS, execute_tool


SYSTEM_PROMPT = """You are HyperBit, a small physical voice agent whose body is a BBC micro:bit V2 on a Wukong board and whose main home is this PC.

You can use tools to remember things and work inside your own sandboxed workspace. Use tools when they help. Never claim a tool succeeded unless you actually called it.

Your final reply will usually be spoken by a tiny speaker. Keep normal spoken replies concise: preferably one or two short sentences, usually under 30 words. Do not add markdown unless the user specifically asks for something that needs formatting.

You are allowed to have personality, but be useful first.
"""


class HyperAgent:
    def __init__(self, home_dir: Path, model: str | None = None):
        key = os.environ.get("HYPER_API_KEY")
        if not key:
            raise RuntimeError("Set HYPER_API_KEY to your sk-hyper-... key first.")
        self.base_url = os.environ.get("HYPER_BASE_URL", "https://hyper.charm.land/v1").rstrip("/")
        self.client = httpx.Client(timeout=90.0, headers={"Authorization": f"Bearer {key}"})
        self.home = AgentHome(home_dir)
        self.model = model or os.environ.get("HYPER_MODEL", "deepseek-v4-flash")
        self.history_path = self.home.root / "conversation.json"
        self.messages = self._load_history()

    def _load_history(self):
        if self.history_path.exists():
            try:
                history = json.loads(self.history_path.read_text(encoding="utf-8"))
                if isinstance(history, list):
                    return history[-30:]
            except Exception:
                pass
        return []

    def _save_history(self):
        self.history_path.write_text(json.dumps(self.messages[-30:], indent=2), encoding="utf-8")

    def available_models(self):
        try:
            r = self.client.get(f"{self.base_url}/models")
            r.raise_for_status()
            return [m["id"] for m in r.json().get("data", []) if isinstance(m, dict) and m.get("id")]
        except Exception:
            return []

    def resolve_model(self):
        models = self.available_models()
        if models and self.model not in models:
            print(f"[hyper] configured model {self.model!r} not found; using {models[0]!r}")
            self.model = models[0]
        return self.model

    def ask(self, text: str) -> tuple[str, dict]:
        self.messages.append({"role": "user", "content": text})
        usage = {}
        for _ in range(8):
            payload = {
                "model": self.model,
                "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + self.messages[-30:],
                "tools": TOOL_DEFS,
                "tool_choice": "auto",
                "temperature": 0.4,
                "max_tokens": 350,
            }
            r = self.client.post(f"{self.base_url}/chat/completions", json=payload)
            if r.status_code >= 400:
                raise RuntimeError(f"Hyper HTTP {r.status_code}: {r.text[:500]}")
            body = r.json()
            usage = body.get("usage") or {}
            choice = (body.get("choices") or [{}])[0]
            msg = choice.get("message") or {}
            tool_calls = msg.get("tool_calls") or []

            if tool_calls:
                assistant_msg = {
                    "role": "assistant",
                    "content": msg.get("content"),
                    "tool_calls": tool_calls,
                }
                self.messages.append(assistant_msg)
                for call in tool_calls:
                    fn = (call.get("function") or {})
                    name = fn.get("name", "")
                    raw = fn.get("arguments") or "{}"
                    try:
                        args = json.loads(raw)
                    except json.JSONDecodeError:
                        args = {}
                    try:
                        result = execute_tool(self.home, name, args)
                    except Exception as exc:
                        result = {"error": str(exc)}
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": call.get("id"),
                        "content": json.dumps(result, ensure_ascii=False),
                    })
                continue

            reply = (msg.get("content") or "").strip()
            if not reply:
                reply = "I don't have a spoken response for that."
            self.messages.append({"role": "assistant", "content": reply})
            self._save_history()
            return reply, usage

        raise RuntimeError("Agent exceeded the tool-call loop limit.")
