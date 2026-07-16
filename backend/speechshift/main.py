from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from speechshift.config import Settings, SpeechProvider, get_settings
from speechshift.models import PublicConfig, ReplayRunRequest, SessionCreated
from speechshift.replay import ReplayCatalogue, ReplayProvider
from speechshift.sessions import SessionStore

LOGGER = logging.getLogger("speechshift")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    catalogue = ReplayCatalogue(settings.replay_asset_dir)
    replay_provider = ReplayProvider(catalogue)
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
            "provider": settings.speech_provider,
            "replay_ready": True,
            "live_provider_ready": False,
            "storage": "memory-only",
        }

    @app.get("/api/config", response_model=PublicConfig)
    async def public_config() -> PublicConfig:
        providers = [
            {"id": "replay", "label": "Replay", "state": "ready", "detail": "Prepared offline examples"},
            {"id": "local", "label": "Local", "state": "not-configured", "detail": "Model spike pending"},
            {
                "id": "modeldeck",
                "label": "ModelDeck",
                "state": "not-configured",
                "detail": "Speech capability not yet rehearsed",
            },
        ]
        return PublicConfig(
            demo_name=settings.demo_name,
            demo_mode=settings.demo_mode,
            provider=settings.speech_provider,
            provider_label=(
                "Replay mode" if settings.speech_provider is SpeechProvider.REPLAY else "Live provider"
            ),
            audio_sample_rate=settings.audio_sample_rate,
            max_input_seconds=settings.max_input_seconds,
            safe_output_volume=settings.safe_output_volume,
            port_allocation_confirmed=settings.port_allocation_confirmed,
            providers=providers,
        )

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

        async def send(event: dict[str, Any]) -> None:
            await websocket.send_json(event)

        try:
            while True:
                message = await websocket.receive_json()
                command = message.get("command")
                if command == "start":
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
                elif command == "cancel":
                    session.cancelled.set()
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
