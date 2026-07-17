from __future__ import annotations

import asyncio
import math
import sys
import time
from array import array
from collections.abc import Awaitable, Callable
from typing import Any

from speechshift.models import LocalRunRequest
from speechshift.sessions import Session

SendJson = Callable[[dict[str, Any]], Awaitable[None]]
SendBytes = Callable[[bytes], Awaitable[None]]

PROFILE_LABELS = {
    "calm-narrator": "Calm DSP",
    "energetic-presenter": "Energetic DSP",
    "robot": "Artificial robot DSP",
    "anonymised-voice": "Anonymised voice",
}

PROFILE_DESCRIPTIONS = {
    "calm-narrator": "A slower, steadier signal-processing effect",
    "energetic-presenter": "A quicker, brighter signal-processing effect",
    "robot": "A clearly artificial electronic effect",
    "anonymised-voice": "Experimental formant reshaping that keeps the recording's timing",
}


class LocalDspProvider:
    OUTPUT_CHUNK_BYTES = 6_400

    async def run(
        self,
        session: Session,
        request: LocalRunRequest,
        input_pcm: bytes,
        input_frames: int,
        send_json: SendJson,
        send_bytes: SendBytes,
    ) -> None:
        generation = session.generation
        started = time.perf_counter()

        async def emit(event_type: str, **payload: Any) -> None:
            if session.cancelled.is_set() or generation != session.generation:
                raise asyncio.CancelledError
            await send_json(
                {
                    "type": event_type,
                    "sequence": session.next_sequence(),
                    "session_id": session.id,
                    "generation": generation,
                    "dsp": True,
                    **payload,
                }
            )

        try:
            await emit("state", state="processing", stage="spoken", detail="Local PCM received")
            await asyncio.sleep(0)
            output_pcm = transform_pcm16(
                input_pcm,
                sample_rate=request.audio_format.sample_rate_hz,
                profile=request.selection_id,
            )
            processing_ms = round((time.perf_counter() - started) * 1000)
            await emit(
                "state",
                state="dsp_profile_applied",
                stage="generated",
                detail=PROFILE_LABELS[request.selection_id],
            )
            await emit(
                "audio_start",
                stage="generated",
                label=PROFILE_LABELS[request.selection_id],
                audio_format={
                    "encoding": "pcm_s16le",
                    "sample_rate_hz": request.audio_format.sample_rate_hz,
                    "channels": 1,
                },
            )
            output_sequence = 1
            for offset in range(0, len(output_pcm), self.OUTPUT_CHUNK_BYTES):
                if session.cancelled.is_set() or generation != session.generation:
                    raise asyncio.CancelledError
                await send_bytes(
                    output_sequence.to_bytes(4, "little")
                    + output_pcm[offset : offset + self.OUTPUT_CHUNK_BYTES]
                )
                output_sequence += 1
                await asyncio.sleep(0)
            await emit("audio_end", stage="generated", frames=output_sequence - 1)
            input_duration_ms = round(
                len(input_pcm) / (request.audio_format.sample_rate_hz * 2) * 1000
            )
            await emit(
                "metrics",
                input_audio_ms=input_duration_ms,
                input_frames=input_frames,
                first_audio_latency_ms=processing_ms,
                dsp_processing=True,
            )
            await emit("complete", state="complete")
        except asyncio.CancelledError:
            return


def transform_pcm16(pcm: bytes, sample_rate: int, profile: str) -> bytes:
    if profile not in PROFILE_LABELS:
        raise ValueError("unsupported DSP profile")
    if len(pcm) % 2:
        raise ValueError("PCM16 input must contain complete samples")
    samples = array("h")
    samples.frombytes(pcm)
    if sys.byteorder != "little":
        samples.byteswap()
    floats = [sample / 32768.0 for sample in samples]

    if profile == "calm-narrator":
        processed = _pitch_resample(floats, factor=0.90)
        processed = _low_pass(processed, smoothing=0.32)
    elif profile == "energetic-presenter":
        processed = _pitch_resample(floats, factor=1.10)
        processed = [math.tanh(sample * 1.35) for sample in processed]
    elif profile == "robot":
        processed = [
            sample * (0.38 + 0.72 * math.cos(2 * math.pi * 30 * index / sample_rate))
            for index, sample in enumerate(floats)
        ]
    else:
        processed = _mcadams_formant_shift(floats, sample_rate, coefficient=0.82)

    prepared = _prepare_playback(processed, sample_rate, ceiling=0.82)
    output = array("h", (round(sample * 32767) for sample in prepared))
    if sys.byteorder != "little":
        output.byteswap()
    return output.tobytes()


def _pitch_resample(samples: list[float], factor: float) -> list[float]:
    if not samples:
        return []
    output_length = max(1, round(len(samples) / factor))
    output: list[float] = []
    for index in range(output_length):
        position = min(index * factor, len(samples) - 1)
        before = int(position)
        after = min(before + 1, len(samples) - 1)
        fraction = position - before
        output.append(samples[before] * (1 - fraction) + samples[after] * fraction)
    return output


def _low_pass(samples: list[float], smoothing: float) -> list[float]:
    if not samples:
        return []
    output = [samples[0]]
    for sample in samples[1:]:
        output.append(output[-1] + smoothing * (sample - output[-1]))
    return output


def _mcadams_formant_shift(
    samples: list[float], sample_rate: int, coefficient: float
) -> list[float]:
    """Reshape LPC pole angles while preserving sample count.

    This is an independent, standard-library implementation of the McAdams
    coefficient technique used by the VoicePrivacy B2 baseline. It operates on
    overlapping frames and never derives words or a speaker identity.
    """
    if not samples:
        return []
    frame_size = max(64, round(sample_rate * 0.03))
    if frame_size % 2:
        frame_size += 1
    hop_size = frame_size // 2
    order = min(12, frame_size // 4)
    padding = hop_size
    padded = [0.0] * padding + samples + [0.0] * (padding + frame_size)
    output = [0.0] * len(padded)
    normalisation = [0.0] * len(padded)
    window = [
        0.5 - 0.5 * math.cos(2 * math.pi * index / (frame_size - 1))
        for index in range(frame_size)
    ]

    final_start = len(padded) - frame_size
    for start in range(0, final_start + 1, hop_size):
        frame = [padded[start + index] * window[index] for index in range(frame_size)]
        analysis = _lpc_coefficients(frame, order)
        shifted = _shift_lpc_poles(analysis, coefficient)
        residual = _fir_prediction_error(frame, analysis)
        synthesised = _all_pole_synthesis(residual, shifted)
        for index, sample in enumerate(synthesised):
            weight = window[index]
            output[start + index] += sample * weight
            normalisation[start + index] += weight * weight

    restored = [
        output[index] / normalisation[index] if normalisation[index] > 1e-8 else 0.0
        for index in range(padding, padding + len(samples))
    ]
    return restored


def _lpc_coefficients(samples: list[float], order: int) -> list[float]:
    autocorrelation = [
        sum(samples[index] * samples[index - lag] for index in range(lag, len(samples)))
        for lag in range(order + 1)
    ]
    if autocorrelation[0] < 1e-10:
        return [0.0] * order

    coefficients = [0.0] * order
    error = autocorrelation[0]
    for step in range(order):
        numerator = autocorrelation[step + 1]
        for index in range(step):
            numerator += coefficients[index] * autocorrelation[step - index]
        reflection = max(-0.98, min(0.98, -numerator / max(error, 1e-12)))
        previous = coefficients.copy()
        coefficients[step] = reflection
        for index in range(step):
            coefficients[index] = previous[index] + reflection * previous[step - index - 1]
        error *= max(1e-6, 1.0 - reflection * reflection)
    return coefficients


def _shift_lpc_poles(coefficients: list[float], coefficient: float) -> list[float]:
    if not any(coefficients):
        return coefficients.copy()
    roots = _polynomial_roots([1.0, *coefficients])
    if len(roots) != len(coefficients):
        return coefficients.copy()
    shifted_roots: list[complex] = []
    for root in roots:
        radius = min(abs(root), 0.98)
        angle = math.atan2(root.imag, root.real)
        if abs(angle) > 1e-5:
            angle = math.copysign(abs(angle) ** coefficient, angle)
        shifted_roots.append(radius * complex(math.cos(angle), math.sin(angle)))
    polynomial: list[complex] = [1.0 + 0.0j]
    for root in shifted_roots:
        expanded = [0.0j] * (len(polynomial) + 1)
        for index, value in enumerate(polynomial):
            expanded[index] += value
            expanded[index + 1] -= value * root
        polynomial = expanded
    shifted = [value.real for value in polynomial[1:]]
    return shifted if all(math.isfinite(value) for value in shifted) else coefficients.copy()


def _polynomial_roots(coefficients: list[float]) -> list[complex]:
    """Find roots of a monic polynomial with deterministic Durand-Kerner iterations."""
    degree = len(coefficients) - 1
    radius = 0.9
    roots = [
        radius * complex(math.cos(2 * math.pi * index / degree), math.sin(2 * math.pi * index / degree))
        for index in range(degree)
    ]
    for _ in range(40):
        maximum_change = 0.0
        updated: list[complex] = []
        for index, root in enumerate(roots):
            value = complex(coefficients[0])
            for item in coefficients[1:]:
                value = value * root + item
            denominator = 1.0 + 0.0j
            for other_index, other in enumerate(roots):
                if other_index != index:
                    denominator *= root - other
            if abs(denominator) < 1e-12:
                denominator = complex(1e-12, 1e-12)
            replacement = root - value / denominator
            if not math.isfinite(replacement.real) or not math.isfinite(replacement.imag):
                return []
            updated.append(replacement)
            maximum_change = max(maximum_change, abs(replacement - root))
        roots = updated
        if maximum_change < 1e-7:
            break
    return roots


def _fir_prediction_error(samples: list[float], coefficients: list[float]) -> list[float]:
    output: list[float] = []
    for index, sample in enumerate(samples):
        predicted = sum(
            coefficient * samples[index - lag]
            for lag, coefficient in enumerate(coefficients, start=1)
            if index >= lag
        )
        output.append(sample + predicted)
    return output


def _all_pole_synthesis(samples: list[float], coefficients: list[float]) -> list[float]:
    output: list[float] = []
    for index, sample in enumerate(samples):
        feedback = sum(
            coefficient * output[index - lag]
            for lag, coefficient in enumerate(coefficients, start=1)
            if index >= lag
        )
        output.append(max(-4.0, min(4.0, sample - feedback)))
    return output


def _prepare_playback(samples: list[float], sample_rate: int, ceiling: float) -> list[float]:
    if not samples:
        return []
    peak = max(abs(sample) for sample in samples)
    scale = ceiling / peak if peak > ceiling else 1.0
    output = [max(-ceiling, min(ceiling, sample * scale)) for sample in samples]
    fade_samples = min(round(sample_rate * 0.01), len(output) // 4)
    if fade_samples > 1:
        for index in range(fade_samples):
            gain = index / (fade_samples - 1)
            output[index] *= gain
            output[-index - 1] *= gain
    return output
