from __future__ import annotations

import math
import sys
from array import array
from dataclasses import dataclass


@dataclass(frozen=True)
class AudioActivity:
    duration_ms: int
    active_ms: int
    peak_dbfs: float
    rms_dbfs: float

    @property
    def has_speech(self) -> bool:
        return self.active_ms >= 120


def analyse_pcm16_activity(
    pcm: bytes,
    sample_rate: int,
    *,
    window_ms: int = 20,
    activity_threshold_dbfs: float = -42.0,
) -> AudioActivity:
    """Measure useful input activity without retaining or transcribing visitor audio."""
    if sample_rate < 1:
        raise ValueError("sample_rate must be positive")
    if len(pcm) % 2:
        raise ValueError("PCM16 input must contain complete samples")

    samples = array("h")
    samples.frombytes(pcm)
    if sys.byteorder != "little":
        samples.byteswap()
    if not samples:
        return AudioActivity(duration_ms=0, active_ms=0, peak_dbfs=-120.0, rms_dbfs=-120.0)

    window_samples = max(1, round(sample_rate * window_ms / 1_000))
    threshold = 10 ** (activity_threshold_dbfs / 20)
    square_sum = 0.0
    peak = 0.0
    active_samples = 0
    for offset in range(0, len(samples), window_samples):
        window = samples[offset : offset + window_samples]
        normalised = [sample / 32768.0 for sample in window]
        window_square_sum = sum(sample * sample for sample in normalised)
        square_sum += window_square_sum
        peak = max(peak, *(abs(sample) for sample in normalised))
        window_rms = math.sqrt(window_square_sum / len(window))
        if window_rms >= threshold:
            active_samples += len(window)

    rms = math.sqrt(square_sum / len(samples))
    return AudioActivity(
        duration_ms=round(len(samples) / sample_rate * 1_000),
        active_ms=round(active_samples / sample_rate * 1_000),
        peak_dbfs=_dbfs(peak),
        rms_dbfs=_dbfs(rms),
    )


def _dbfs(value: float) -> float:
    return round(20 * math.log10(value), 1) if value > 0 else -120.0
