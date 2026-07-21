from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from speechshift.audio_activity import analyse_pcm16_activity
from speechshift.config import Settings, SpeechProvider, get_settings
from speechshift.local_dsp import PROFILE_DESCRIPTIONS, PROFILE_LABELS, LocalDspProvider
from speechshift.mock_provider import MockSpeechProvider
from speechshift.models import (
    LocalRunRequest,
    MockRunRequest,
    ProviderSelection,
    PublicConfig,
    ReplayRunRequest,
    SessionCreated,
)
from speechshift.providers import ProviderRegistry, ProviderSelectionError
from speechshift.replay import ReplayCatalogue, ReplayProvider
from speechshift.sessions import SessionStore
from speechshift.streaming import AudioStreamError, SequencedPcmBuffer

LOGGER = logging.getLogger("speechshift")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    catalogue = ReplayCatalogue(settings.replay_asset_dir)
    replay_provider = ReplayProvider(catalogue)
    mock_provider = MockSpeechProvider(catalogue)
    local_dsp_provider = LocalDspProvider()
    provider_registry = ProviderRegistry(settings.speech_provider, settings.demo_mode)
    sessions = SessionStore()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        LOGGER.info("SpeechShift started mode=%s provider=%s", settings.demo_mode, settings.speech_provider)
        yield
        await sessions.clear_all()
        LOGGER.info("SpeechShift stopped; in-memory sessions cleared")

    app = FastAPI(
        title="SpeechShift",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.sessions = sessions

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ready",
            "provider": provider_registry.selected,
            "replay_ready": True,
            "live_provider_ready": False,
            "mock_provider_ready": settings.demo_mode.value == "development",
            "local_dsp_ready": settings.demo_mode.value == "development",
            "storage": "memory-only",
        }

    @app.get("/api/config", response_model=PublicConfig)
    async def public_config() -> PublicConfig:
        return PublicConfig(
            demo_name=settings.demo_name,
            demo_mode=settings.demo_mode,
            provider=provider_registry.selected,
            provider_label=provider_registry.label,
            audio_sample_rate=settings.audio_sample_rate,
            max_input_seconds=settings.max_input_seconds,
            visitor_idle_timeout_seconds=settings.visitor_idle_timeout_seconds,
            safe_output_volume=settings.safe_output_volume,
            port_allocation_confirmed=settings.port_allocation_confirmed,
            providers=provider_registry.statuses(),
            local_voice_profiles=[
                {
                    "id": profile_id,
                    "label": label,
                    "description": PROFILE_DESCRIPTIONS[profile_id],
                }
                for profile_id, label in PROFILE_LABELS.items()
            ],
        )

    @app.post("/api/providers/select", response_model=PublicConfig)
    async def select_provider(selection: ProviderSelection) -> PublicConfig:
        try:
            provider_registry.select(selection.provider)
        except ProviderSelectionError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return await public_config()

    @app.get("/api/replay/catalogue")
    async def replay_catalogue() -> dict[str, Any]:
        return catalogue.public_data()

    @app.post("/api/sessions", response_model=SessionCreated, status_code=201)
    async def create_session() -> SessionCreated:
        session = await sessions.create()
        return SessionCreated(session_id=session.id, generation=session.generation)

    @app.delete("/api/sessions/{session_id}", status_code=204)
    async def clear_session(session_id: str) -> None:
        if not await sessions.clear(session_id):
            raise HTTPException(status_code=404, detail="session not found")

    @app.websocket("/ws/sessions/{session_id}")
    async def session_socket(websocket: WebSocket, session_id: str) -> None:
        session = sessions.get(session_id)
        if session is None:
            await websocket.close(code=4404, reason="stale session")
            return
        await websocket.accept()
        active_task: asyncio.Task[None] | None = None
        stream_request: MockRunRequest | LocalRunRequest | None = None
        stream_buffer: SequencedPcmBuffer | None = None
        stream_provider: SpeechProvider | None = None

        async def send(event: dict[str, Any]) -> None:
            await websocket.send_json(event)

        try:
            while True:
                packet = await websocket.receive()
                if packet["type"] == "websocket.disconnect":
                    raise WebSocketDisconnect(packet.get("code", 1000))
                binary = packet.get("bytes")
                if binary is not None:
                    if stream_buffer is None:
                        await send({"type": "error", "code": "unexpected_audio_frame", "recoverable": True})
                        continue
                    try:
                        stream_buffer.append(binary)
                    except AudioStreamError as error:
                        stream_buffer.clear()
                        stream_buffer = None
                        stream_request = None
                        stream_provider = None
                        await send({"type": "error", "code": error.code, "recoverable": True})
                    continue
                try:
                    message = json.loads(packet.get("text") or "{}")
                except json.JSONDecodeError:
                    await send({"type": "error", "code": "invalid_json", "recoverable": True})
                    continue
                command = message.get("command")
                if command == "start":
                    if provider_registry.selected is not SpeechProvider.REPLAY:
                        await send({"type": "error", "code": "provider_mismatch", "recoverable": True})
                        continue
                    if active_task and not active_task.done():
                        await send({"type": "error", "code": "already_running", "recoverable": True})
                        continue
                    session.cancelled = asyncio.Event()
                    session.sequence = 0
                    try:
                        request = ReplayRunRequest.model_validate(message.get("request"))
                        catalogue.resolve(request)
                    except ValueError:
                        await send({"type": "error", "code": "invalid_replay_request", "recoverable": True})
                        continue
                    active_task = asyncio.create_task(replay_provider.run(session, request, send))
                elif command == "start_mock":
                    if provider_registry.selected is not SpeechProvider.MOCK_MODELDECK:
                        await send({"type": "error", "code": "provider_mismatch", "recoverable": True})
                        continue
                    if active_task and not active_task.done():
                        await send({"type": "error", "code": "already_running", "recoverable": True})
                        continue
                    try:
                        request = MockRunRequest.model_validate(message.get("request"))
                        catalogue.resolve(request)
                    except ValueError:
                        await send({"type": "error", "code": "invalid_mock_request", "recoverable": True})
                        continue
                    if (
                        request.audio_format.encoding != "pcm_s16le"
                        or request.audio_format.sample_rate_hz != settings.audio_sample_rate
                        or request.audio_format.channels != settings.audio_channels
                    ):
                        await send({"type": "error", "code": "unsupported_audio_format", "recoverable": True})
                        continue
                    session.cancelled = asyncio.Event()
                    session.sequence = 0
                    stream_request = request
                    maximum_bytes = (
                        settings.audio_sample_rate
                        * settings.audio_channels
                        * 2
                        * settings.max_input_seconds
                    )
                    stream_buffer = SequencedPcmBuffer(maximum_bytes)
                    stream_provider = SpeechProvider.MOCK_MODELDECK
                    await send(
                        {
                            "type": "state",
                            "state": "receiving_audio",
                            "stage": "spoken",
                            "session_id": session.id,
                            "generation": session.generation,
                            "mock": True,
                        }
                    )
                elif command == "start_local":
                    if provider_registry.selected is not SpeechProvider.LOCAL:
                        await send({"type": "error", "code": "provider_mismatch", "recoverable": True})
                        continue
                    if active_task and not active_task.done():
                        await send({"type": "error", "code": "already_running", "recoverable": True})
                        continue
                    try:
                        request = LocalRunRequest.model_validate(message.get("request"))
                    except ValueError:
                        await send({"type": "error", "code": "invalid_local_request", "recoverable": True})
                        continue
                    if request.selection_id not in PROFILE_LABELS:
                        await send({"type": "error", "code": "invalid_profile", "recoverable": True})
                        continue
                    if (
                        request.audio_format.encoding != "pcm_s16le"
                        or request.audio_format.sample_rate_hz != settings.audio_sample_rate
                        or request.audio_format.channels != settings.audio_channels
                    ):
                        await send({"type": "error", "code": "unsupported_audio_format", "recoverable": True})
                        continue
                    session.cancelled = asyncio.Event()
                    session.sequence = 0
                    stream_request = request
                    maximum_bytes = (
                        settings.audio_sample_rate
                        * settings.audio_channels
                        * 2
                        * settings.max_input_seconds
                    )
                    stream_buffer = SequencedPcmBuffer(maximum_bytes)
                    stream_provider = SpeechProvider.LOCAL
                    await send(
                        {
                            "type": "state",
                            "state": "receiving_audio",
                            "stage": "spoken",
                            "session_id": session.id,
                            "generation": session.generation,
                            "dsp": True,
                        }
                    )
                elif command == "end_audio":
                    if stream_request is None or stream_buffer is None or stream_provider is None:
                        await send({"type": "error", "code": "audio_stream_not_started", "recoverable": True})
                        continue
                    if stream_buffer.length < settings.audio_sample_rate * 2 // 10:
                        stream_buffer.clear()
                        stream_buffer = None
                        stream_request = None
                        stream_provider = None
                        await send({"type": "error", "code": "audio_too_short", "recoverable": True})
                        continue
                    input_frames = stream_buffer.frame_count
                    input_pcm = stream_buffer.consume()
                    request = stream_request
                    selected_stream_provider = stream_provider
                    stream_buffer = None
                    stream_request = None
                    stream_provider = None
                    activity = analyse_pcm16_activity(
                        input_pcm,
                        sample_rate=request.audio_format.sample_rate_hz,
                    )
                    if not activity.has_speech:
                        await send({"type": "error", "code": "audio_silent", "recoverable": True})
                        continue
                    if selected_stream_provider is SpeechProvider.LOCAL:
                        active_task = asyncio.create_task(
                            local_dsp_provider.run(
                                session,
                                request,
                                input_pcm,
                                input_frames,
                                send,
                                websocket.send_bytes,
                            )
                        )
                    else:
                        active_task = asyncio.create_task(
                            mock_provider.run(
                                session,
                                request,
                                input_pcm,
                                input_frames,
                                send,
                                websocket.send_bytes,
                            )
                        )
                elif command == "cancel":
                    session.cancelled.set()
                    if stream_buffer is not None:
                        stream_buffer.clear()
                    stream_buffer = None
                    stream_request = None
                    stream_provider = None
                    if active_task:
                        active_task.cancel()
                    await send(
                        {
                            "type": "cancelled",
                            "session_id": session.id,
                            "generation": session.generation,
                        }
                    )
                else:
                    await send({"type": "error", "code": "unknown_command", "recoverable": True})
        except WebSocketDisconnect:
            session.cancelled.set()
            if active_task:
                active_task.cancel()

    replay_root = settings.replay_asset_dir.resolve()
    app.mount("/replay", StaticFiles(directory=replay_root), name="replay")

    frontend_dist = Path("frontend/dist").resolve()
    if frontend_dist.is_dir():
        app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="frontend-assets")

        @app.get("/{path:path}", include_in_schema=False)
        async def frontend(path: str) -> FileResponse:
            candidate = frontend_dist / path
            if path and candidate.is_file() and frontend_dist in candidate.resolve().parents:
                return FileResponse(candidate)
            return FileResponse(frontend_dist / "index.html")

    return app
