from __future__ import annotations

import asyncio
import math
import sys
import time
from array import array
from collections.abc import Awaitable, Callable
from typing import Any

from speechshift.models import MockRunRequest
from speechshift.sessions import Session

SendJson = Callable[[dict[str, Any]], Awaitable[None]]
SendBytes = Callable[[bytes], Awaitable[None]]

PROFILE_LABELS = {
    "calm-narrator": "Calm DSP",
    "energetic-presenter": "Energetic DSP",
    "robot": "Artificial robot DSP",
}


class LocalDspProvider:
    OUTPUT_CHUNK_BYTES = 6_400

    async def run(
        self,
        session: Session,
        request: MockRunRequest,
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
    else:
        processed = [
            sample * (0.38 + 0.72 * math.cos(2 * math.pi * 30 * index / sample_rate))
            for index, sample in enumerate(floats)
        ]

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
