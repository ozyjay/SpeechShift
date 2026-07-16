from __future__ import annotations

import asyncio
import wave
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from speechshift.models import MockRunRequest, ReplayRunRequest
from speechshift.replay import ReplayCatalogue
from speechshift.sessions import Session

SendJson = Callable[[dict[str, Any]], Awaitable[None]]
SendBytes = Callable[[bytes], Awaitable[None]]


class MockSpeechProvider:
    OUTPUT_CHUNK_BYTES = 6_400

    def __init__(self, catalogue: ReplayCatalogue) -> None:
        self._catalogue = catalogue

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
        sentence, selection = self._catalogue.resolve(
            ReplayRunRequest(
                mode=request.mode,
                sentence_id=request.sentence_id,
                selection_id=request.selection_id,
            )
        )

        async def emit(event_type: str, **payload: Any) -> None:
            if session.cancelled.is_set() or generation != session.generation:
                raise asyncio.CancelledError
            await send_json(
                {
                    "type": event_type,
                    "sequence": session.next_sequence(),
                    "session_id": session.id,
                    "generation": generation,
                    "mock": True,
                    **payload,
                }
            )

        try:
            await emit("state", state="processing", stage="spoken", detail="Mock received bounded PCM")
            await asyncio.sleep(0.15)
            partial = sentence["source_text"].split(" ")
            await emit(
                "transcript_partial",
                text=" ".join(partial[: max(2, len(partial) // 2)]),
                stage="recognised",
            )
            await asyncio.sleep(0.15)
            await emit("transcript_final", text=sentence["source_text"], stage="recognised", fixture=True)
            if request.mode.value == "language":
                await asyncio.sleep(0.15)
                await emit("translation_final", text=selection["text"], stage="translated", fixture=True)
            else:
                await emit(
                    "state",
                    state="mock_profile_selected",
                    stage="generated",
                    detail=f"Fixture: {selection['description']}",
                )
            await asyncio.sleep(0.15)
            pcm, sample_rate = self._read_fixture(self._catalogue.asset_dir / selection["audio"])
            await emit(
                "audio_start",
                stage="generated",
                label=f"Mock fixture · {selection['label']}",
                audio_format={"encoding": "pcm_s16le", "sample_rate_hz": sample_rate, "channels": 1},
            )
            output_sequence = 1
            for offset in range(0, len(pcm), self.OUTPUT_CHUNK_BYTES):
                if session.cancelled.is_set() or generation != session.generation:
                    raise asyncio.CancelledError
                chunk = pcm[offset : offset + self.OUTPUT_CHUNK_BYTES]
                await send_bytes(output_sequence.to_bytes(4, "little") + chunk)
                output_sequence += 1
                await asyncio.sleep(0)
            await emit("audio_end", stage="generated", frames=output_sequence - 1)
            bytes_per_second = (
                request.audio_format.sample_rate_hz * request.audio_format.channels * 2
            )
            input_duration_ms = round(len(input_pcm) / bytes_per_second * 1000)
            await emit(
                "metrics",
                input_audio_ms=input_duration_ms,
                input_frames=input_frames,
                first_audio_latency_ms=600,
                mock_timing=True,
            )
            await emit("complete", state="complete")
        except asyncio.CancelledError:
            return

    @staticmethod
    def _read_fixture(path: Path) -> tuple[bytes, int]:
        with wave.open(str(path), "rb") as fixture:
            if fixture.getnchannels() != 1 or fixture.getsampwidth() != 2:
                raise ValueError("mock fixture must be mono PCM16 WAV")
            return fixture.readframes(fixture.getnframes()), fixture.getframerate()
