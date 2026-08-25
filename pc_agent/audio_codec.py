from __future__ import annotations
import numpy as np

STEP_TABLE = np.array([
    7,8,9,10,11,12,13,14,16,17,19,21,23,25,28,31,
    34,37,41,45,50,55,60,66,73,80,88,97,107,118,130,143,
    157,173,190,209,230,253,279,307,337,371,408,449,494,544,
    598,658,724,796,876,963,1060,1166,1282,1411,1552,1707,1878,2066,
    2272,2499,2749,3024,3327,3660,4026,4428,4871,5358,5894,6484,7132,7845,
    8630,9493,10442,11487,12635,13899,15289,16818,18500,20350,22385,24623,
    27086,29794,32767
], dtype=np.int32)

INDEX_TABLE = np.array([
    -1,-1,-1,-1,2,4,6,8,
    -1,-1,-1,-1,2,4,6,8
], dtype=np.int32)


def _decode_nibble(nibble: int, predictor: int, index: int):
    step = int(STEP_TABLE[index])
    diff = step >> 3
    if nibble & 4:
        diff += step
    if nibble & 2:
        diff += step >> 1
    if nibble & 1:
        diff += step >> 2
    if nibble & 8:
        predictor -= diff
    else:
        predictor += diff
    predictor = max(-32768, min(32767, predictor))
    index += int(INDEX_TABLE[nibble & 0xF])
    index = max(0, min(88, index))
    return predictor, index


def decode_ima_adpcm(data: bytes, sample_count: int | None = None) -> np.ndarray:
    predictor = 0
    index = 0
    out = np.empty(len(data) * 2, dtype=np.int16)
    p = 0
    for byte in data:
        predictor, index = _decode_nibble(byte & 0x0F, predictor, index)
        out[p] = predictor
        p += 1
        predictor, index = _decode_nibble((byte >> 4) & 0x0F, predictor, index)
        out[p] = predictor
        p += 1
    if sample_count is not None:
        out = out[:sample_count]
    return out


def _encode_sample(sample: int, predictor: int, index: int):
    step = int(STEP_TABLE[index])
    diff = int(sample) - predictor
    nibble = 0
    if diff < 0:
        nibble = 8
        diff = -diff
    delta = 0
    vpdiff = step >> 3
    if diff >= step:
        delta |= 4
        diff -= step
        vpdiff += step
    if diff >= (step >> 1):
        delta |= 2
        diff -= step >> 1
        vpdiff += step >> 1
    if diff >= (step >> 2):
        delta |= 1
        vpdiff += step >> 2
    nibble |= delta
    if nibble & 8:
        predictor -= vpdiff
    else:
        predictor += vpdiff
    predictor = max(-32768, min(32767, predictor))
    index += int(INDEX_TABLE[nibble & 0x0F])
    index = max(0, min(88, index))
    return nibble, predictor, index


def encode_ima_adpcm(samples: np.ndarray) -> bytes:
    samples = np.asarray(samples, dtype=np.int16).reshape(-1)
    predictor = 0
    index = 0
    out = bytearray((len(samples) + 1) // 2)
    for i in range(0, len(samples), 2):
        low, predictor, index = _encode_sample(int(samples[i]), predictor, index)
        high = 0
        if i + 1 < len(samples):
            high, predictor, index = _encode_sample(int(samples[i + 1]), predictor, index)
        out[i // 2] = low | (high << 4)
    return bytes(out)


def resample_int16(samples: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    samples = np.asarray(samples, dtype=np.int16).reshape(-1)
    if src_rate == dst_rate or len(samples) == 0:
        return samples.copy()
    dst_len = max(1, round((len(samples) / float(src_rate)) * dst_rate))
    src_x = np.linspace(0.0, 1.0, len(samples), endpoint=False)
    dst_x = np.linspace(0.0, 1.0, dst_len, endpoint=False)
    out = np.interp(dst_x, src_x, samples.astype(np.float32))
    return np.clip(out, -32768, 32767).astype(np.int16)
