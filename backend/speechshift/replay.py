from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from speechshift.models import ReplayRunRequest
from speechshift.sessions import Session

SendEvent = Callable[[dict[str, Any]], Awaitable[None]]


class ReplayCatalogue:
    def __init__(self, asset_dir: Path) -> None:
        self.asset_dir = asset_dir
        catalogue_path = asset_dir / "catalogue.json"
        if not catalogue_path.is_file():
            raise ValueError(f"required replay catalogue is missing: {catalogue_path}")
        self.data: dict[str, Any] = json.loads(catalogue_path.read_text(encoding="utf-8"))
        self._validate_assets()

    def _validate_assets(self) -> None:
        sentences = self.data.get("sentences", [])
        if len(sentences) < 3:
            raise ValueError("replay catalogue requires at least three source sentences")
        for sentence in sentences:
            paths = [sentence["original_audio"]]
            paths.extend(item["audio"] for item in sentence.get("voices", []))
            paths.extend(item["audio"] for item in sentence.get("languages", []))
            if len(sentence.get("voices", [])) < 3 or len(sentence.get("languages", [])) < 2:
                raise ValueError("each replay sentence requires three voices and two languages")
            for relative_path in paths:
                if not (self.asset_dir / relative_path).is_file():
                    raise ValueError(f"required replay asset is missing: {relative_path}")

    def public_data(self) -> dict[str, Any]:
        return self.data

    def resolve(self, request: ReplayRunRequest) -> tuple[dict[str, Any], dict[str, Any]]:
        sentence = next(
            (item for item in self.data["sentences"] if item["id"] == request.sentence_id), None
        )
        if sentence is None:
            raise ValueError("unknown replay sentence")
        collection = "voices" if request.mode.value == "voice" else "languages"
        selection = next(
            (item for item in sentence[collection] if item["id"] == request.selection_id), None
        )
        if selection is None:
            raise ValueError("unknown replay selection")
        return sentence, selection


class ReplayProvider:
    def __init__(self, catalogue: ReplayCatalogue) -> None:
        self.catalogue = catalogue

    async def run(self, session: Session, request: ReplayRunRequest, send: SendEvent) -> None:
        sentence, selection = self.catalogue.resolve(request)
        generation = session.generation
        started = asyncio.get_running_loop().time()

        async def emit(event_type: str, **payload: Any) -> None:
            if session.cancelled.is_set() or generation != session.generation:
                raise asyncio.CancelledError
            await send(
                {
                    "type": event_type,
                    "sequence": session.next_sequence(),
                    "session_id": session.id,
                    "generation": generation,
                    **payload,
                }
            )

        try:
            await emit("state", state="receiving_audio", stage="spoken")
            await asyncio.sleep(0.45)
            await emit(
                "audio",
                stage="spoken",
                audio_url=f"/replay/{sentence['original_audio']}",
                label="Prepared source audio",
            )
            await asyncio.sleep(0.45)
            await emit("transcript_final", text=sentence["source_text"], stage="recognised")
            await asyncio.sleep(0.55)
            if request.mode.value == "language":
                await emit("translation_final", text=selection["text"], stage="translated")
                await asyncio.sleep(0.55)
            else:
                await emit(
                    "state",
                    state="voice_characteristics_selected",
                    stage="generated",
                    detail=selection["description"],
                )
                await asyncio.sleep(0.45)
            latency_ms = round((asyncio.get_running_loop().time() - started) * 1000)
            await emit(
                "audio",
                stage="generated",
                audio_url=f"/replay/{selection['audio']}",
                label=selection["label"],
                autoplay=True,
            )
            await emit(
                "metrics",
                input_audio_ms=sentence["duration_ms"],
                first_audio_latency_ms=latency_ms,
                replay_timing=True,
            )
            await emit("complete", state="complete")
        except asyncio.CancelledError:
            return

