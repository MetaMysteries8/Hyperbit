from __future__ import annotations
from pathlib import Path
import argparse
import asyncio
import os

from audio_codec import decode_ima_adpcm
from ble_link import (
    BLEDisconnectedError,
    HyperBitBLE,
    STATE_IDLE,
    STATE_TRANSCRIBING,
    STATE_THINKING,
    STATE_SPEAKING,
    STATE_ERROR,
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


async def ble_test_mode(args):
    """Validate only firmware/BLE transport; no API key, STT, model, or TTS."""
    ble = HyperBitBLE(args.name, args.address)
    try:
        await ble.connect()
        print("[ble-test] HELLO/READY succeeded")
        print(
            f"[ble-test] firmware revision={ble.firmware_revision} "
            f"capabilities=0x{ble.capabilities:02x}"
        )
        # Catch boards that complete the handshake and immediately fall off.
        await asyncio.sleep(2.0)
        if not ble.is_connected():
            raise BLEDisconnectedError("connection dropped during the 2-second stability check")
        print("[ble-test] connection remained stable for 2 seconds")
    finally:
        await ble.close()


async def _connected_voice_session(ble, agent, stt, tts, state):
    operation_lock = asyncio.Lock()

    async def replay_worker():
        while True:
            await ble.next_replay_request()
            async with operation_lock:
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
            async with operation_lock:
                ble.clear_cancel()

                if not utt.adpcm:
                    print("[stt] empty utterance")
                    continue

                if utt.overflow:
                    print("[mic] warning: microphone/BLE audio had an overflow or packet gap")

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

                except BLEDisconnectedError:
                    raise
                except Exception as exc:
                    print(f"[error] {exc}")
                    try:
                        await ble.set_state(STATE_ERROR)
                        await asyncio.sleep(1.0)
                        await ble.set_state(STATE_IDLE)
                    except BLEDisconnectedError:
                        raise
                    except Exception:
                        pass
    finally:
        replay_task.cancel()
        try:
            await replay_task
        except (asyncio.CancelledError, BLEDisconnectedError):
            pass


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

    try:
        while True:
            try:
                await _connected_voice_session(ble, agent, stt, tts, state)
            except BLEDisconnectedError as exc:
                print(f"[ble] session lost: {exc}")
                await ble.close()
                print("[ble] automatic recovery enabled; reconnecting until the board returns...")

                while True:
                    try:
                        await asyncio.sleep(2.0)
                        await ble.connect()
                        print("[ble] recovered; voice session resumed")
                        break
                    except asyncio.CancelledError:
                        raise
                    except Exception as reconnect_exc:
                        print(f"[ble] reconnect failed: {reconnect_exc}")
                        print("[ble] retrying in 3 seconds (Ctrl+C to stop)")
                        await ble.close()
                        await asyncio.sleep(3.0)
    finally:
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
    p.add_argument(
        "--ble-test",
        action="store_true",
        help="test only BLE/NUS/firmware identity; does not require a Hyper API key",
    )
    p.add_argument("--home", default=str(DEFAULT_HOME))
    p.add_argument("--model", default=os.environ.get("HYPER_MODEL"))
    p.add_argument("--name", help="optional micro:bit BLE name substring")
    p.add_argument("--address", help="optional BLE address")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        if args.ble_test:
            asyncio.run(ble_test_mode(args))
        elif args.text:
            text_mode(args)
        else:
            asyncio.run(voice_mode(args))
    except KeyboardInterrupt:
        print("\nStopped.")
