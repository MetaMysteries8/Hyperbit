from __future__ import annotations
from pathlib import Path
import argparse
import asyncio
import os

from audio_codec import decode_ima_adpcm
from ble_link import (
    HyperBitBLE,
    STATE_IDLE, STATE_TRANSCRIBING, STATE_THINKING, STATE_SPEAKING, STATE_ERROR,
)
from hyper_client import HyperAgent
from stt import WhisperSTT
from tts import create_tts


HERE = Path(__file__).resolve().parent
DEFAULT_HOME = HERE.parent / "agent_home"


def usage_line(usage: dict) -> str:
    if not usage:
        return ""
    remaining = usage.get("remaining") or {}
    cost = usage.get("cost") or {}
    bits = []
    if cost.get("hypercredits") is not None:
        bits.append(f"cost={cost['hypercredits']} hc")
    if remaining.get("hypercredits") is not None:
        bits.append(f"remaining={remaining['hypercredits']} hc")
    return " ".join(bits)


async def voice_mode(args):
    home = Path(args.home).expanduser()
    agent = HyperAgent(home, args.model)
    agent.resolve_model()
    stt = WhisperSTT()
    tts = create_tts()
    ble = HyperBitBLE(args.name, args.address)

    state = {"last_tts": b""}

    await ble.connect()
    print(f"[agent] Hyper model: {agent.model}")
    print("[controls] hold GOLD LOGO = talk | A = interrupt | B = replay | A+B = mute")

    async def replay_worker():
        while True:
            await ble.next_replay_request()
            if not state["last_tts"]:
                print("[agent] nothing to replay yet")
                continue
            ble.clear_cancel()
            print("[agent] replaying last answer")
            await ble.set_state(STATE_SPEAKING)
            await ble.send_tts(state["last_tts"])
            await ble.set_state(STATE_IDLE)

    replay_task = asyncio.create_task(replay_worker())

    try:
        while True:
            utt = await ble.next_utterance()
            ble.clear_cancel()

            if not utt.adpcm:
                print("[stt] empty utterance")
                continue

            if utt.overflow:
                print("[mic] warning: microphone/BLE ring overflowed during this utterance")

            try:
                await ble.set_state(STATE_TRANSCRIBING)
                pcm = decode_ima_adpcm(utt.adpcm, utt.sample_count or None)
                text = await asyncio.to_thread(stt.transcribe, pcm, 8000)

                if ble.cancelled():
                    print("[agent] cancelled during transcription")
                    await ble.set_state(STATE_IDLE)
                    continue

                if not text:
                    print("[stt] no speech recognized")
                    await ble.set_state(STATE_IDLE)
                    continue

                print(f"\nYOU: {text}")

                await ble.set_state(STATE_THINKING)
                reply, usage = await asyncio.to_thread(agent.ask, text)

                if ble.cancelled():
                    print("[agent] response cancelled; answer will not be spoken")
                    await ble.set_state(STATE_IDLE)
                    continue

                print(f"HYPERBIT: {reply}")
                u = usage_line(usage)
                if u:
                    print(f"[hyper] {u}")

                adpcm = await asyncio.to_thread(tts.synthesize_adpcm, reply, 8000)

                if ble.cancelled():
                    await ble.set_state(STATE_IDLE)
                    continue

                state["last_tts"] = adpcm
                await ble.set_state(STATE_SPEAKING)
                completed = await ble.send_tts(adpcm)
                if not completed:
                    print("[agent] playback interrupted")
                await ble.set_state(STATE_IDLE)

            except Exception as exc:
                print(f"[error] {exc}")
                try:
                    await ble.set_state(STATE_ERROR)
                    await asyncio.sleep(1.0)
                    await ble.set_state(STATE_IDLE)
                except Exception:
                    pass
    finally:
        replay_task.cancel()
        await ble.close()


def text_mode(args):
    home = Path(args.home).expanduser()
    agent = HyperAgent(home, args.model)
    agent.resolve_model()
    reply, usage = agent.ask(args.text)
    print(reply)
    u = usage_line(usage)
    if u:
        print(f"[hyper] {u}")


def parse_args():
    p = argparse.ArgumentParser(description="HyperBit PC-side AI agent")
    p.add_argument("--text", help="test Hyper without BLE/STT/TTS")
    p.add_argument("--home", default=str(DEFAULT_HOME))
    p.add_argument("--model", default=os.environ.get("HYPER_MODEL"))
    p.add_argument("--name", help="optional micro:bit BLE name substring")
    p.add_argument("--address", help="optional BLE address")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.text:
        text_mode(args)
    else:
        try:
            asyncio.run(voice_mode(args))
        except KeyboardInterrupt:
            print("\nStopped.")
