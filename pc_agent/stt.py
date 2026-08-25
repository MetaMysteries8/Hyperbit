from __future__ import annotations
import os
import numpy as np
from audio_codec import resample_int16


class WhisperSTT:
    def __init__(self):
        self.model = None

    def _ensure(self):
        if self.model is not None:
            return
        from faster_whisper import WhisperModel
        model_name = os.environ.get("HYPERBIT_STT_MODEL", "base.en")
        device = os.environ.get("HYPERBIT_STT_DEVICE", "cpu")
        compute = os.environ.get("HYPERBIT_STT_COMPUTE", "int8" if device == "cpu" else "float16")
        print(f"[stt] loading {model_name} on {device}/{compute}")
        self.model = WhisperModel(model_name, device=device, compute_type=compute)

    def transcribe(self, pcm16: np.ndarray, sample_rate: int = 8000) -> str:
        self._ensure()
        pcm16 = resample_int16(pcm16, sample_rate, 16000)
        audio = pcm16.astype(np.float32) / 32768.0
        segments, _info = self.model.transcribe(
            audio,
            language="en",
            vad_filter=True,
            beam_size=1,
            condition_on_previous_text=False,
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        return text
