from __future__ import annotations
from pathlib import Path
import base64
import os
import subprocess
import tempfile
import wave
import numpy as np

from audio_codec import encode_ima_adpcm, resample_int16


def _wav_to_mono_int16(path: Path):
    with wave.open(str(path), "rb") as w:
        channels = w.getnchannels()
        width = w.getsampwidth()
        rate = w.getframerate()
        frames = w.readframes(w.getnframes())

    if width == 2:
        arr = np.frombuffer(frames, dtype="<i2").astype(np.int16)
    elif width == 1:
        arr = ((np.frombuffer(frames, dtype=np.uint8).astype(np.int16) - 128) << 8).astype(np.int16)
    else:
        raise RuntimeError(f"Unsupported WAV sample width: {width}")

    if channels > 1:
        arr = arr.reshape(-1, channels).mean(axis=1).astype(np.int16)
    return arr, rate


class WindowsSapiTTS:
    name = "sapi"

    def synthesize_adpcm(self, text: str, target_rate: int = 8000) -> bytes:
        if os.name != "nt":
            raise RuntimeError("Windows SAPI TTS requires Windows.")

        text = " ".join(text.split())[:600]
        with tempfile.TemporaryDirectory(prefix="hyperbit-tts-") as td:
            td = Path(td)
            txt = td / "say.txt"
            wav = td / "say.wav"
            txt.write_text(text, encoding="utf-8")

            def psq(p: Path):
                return str(p).replace("'", "''")

            script = f"""
Add-Type -AssemblyName System.Speech
$text = Get-Content -Raw -LiteralPath '{psq(txt)}'
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.Rate = 1
$s.Volume = 100
$s.SetOutputToWaveFile('{psq(wav)}')
$s.Speak($text)
$s.Dispose()
"""
            encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
            proc = subprocess.run(
                ["powershell.exe", "-NoProfile", "-EncodedCommand", encoded],
                capture_output=True,
                text=True,
                timeout=45,
            )
            if proc.returncode != 0 or not wav.exists():
                raise RuntimeError(f"SAPI TTS failed: {proc.stderr[-500:]}")
            pcm, src_rate = _wav_to_mono_int16(wav)

        pcm = resample_int16(pcm, src_rate, target_rate)
        # BLE playback is segmented, so the micro:bit never needs this entire
        # response in RAM. Keep only a generous sanity cap on the PC side.
        pcm = pcm[: target_rate * 20]
        return encode_ima_adpcm(pcm)


def create_tts():
    backend = os.environ.get("HYPERBIT_TTS", "sapi").strip().lower()
    if backend in ("sapi", "windows", "windows-sapi"):
        return WindowsSapiTTS()
    raise RuntimeError(
        f"Unknown HYPERBIT_TTS backend: {backend!r}. "
        "The scanned release currently ships Windows SAPI only."
    )
