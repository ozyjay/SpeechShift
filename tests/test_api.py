import asyncio
from pathlib import Path

from httpx import ASGITransport, AsyncClient, MockTransport, Request, Response
from speechshift.config import Settings
from speechshift.main import create_app


def _ready_modeldeck(request: Request) -> Response:
    assert request.url.path == "/v1/routes"
    return Response(
        200,
        json={
            "routes": [
                {"public_name": "speechshift-stt", "ready": True},
                {"public_name": "speechshift-en-fr", "ready": True},
                {"public_name": "speechshift-en-de", "ready": True},
                {"public_name": "speechshift-voice", "ready": True},
            ]
        },
    )


def _unavailable_modeldeck(request: Request) -> Response:
    assert request.url.path == "/v1/routes"
    return Response(200, json={"routes": []})


def test_health_reports_replay_without_claiming_live_readiness() -> None:
    async def scenario() -> None:
        settings = Settings(replay_asset_dir=Path("assets/replay"), _env_file=None)
        app = create_app(settings, modeldeck_transport=MockTransport(_unavailable_modeldeck))
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://speechshift.test") as client:
            response = await client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {
            "status": "ready",
            "provider": "replay",
            "replay_ready": True,
            "live_provider_ready": False,
            "mock_provider_ready": True,
            "local_dsp_ready": True,
            "storage": "memory-only",
        }

    asyncio.run(scenario())


def test_api_creates_and_clears_memory_only_session() -> None:
    async def scenario() -> None:
        settings = Settings(replay_asset_dir=Path("assets/replay"), _env_file=None)
        app = create_app(settings)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://speechshift.test") as client:
            created = await client.post("/api/sessions")
            session_id = created.json()["session_id"]
            cleared = await client.delete(f"/api/sessions/{session_id}")
            missing = await client.delete(f"/api/sessions/{session_id}")
        assert created.status_code == 201
        assert cleared.status_code == 204
        assert missing.status_code == 404

    asyncio.run(scenario())


def test_public_config_keeps_live_providers_visibly_unavailable() -> None:
    async def scenario() -> None:
        settings = Settings(replay_asset_dir=Path("assets/replay"), _env_file=None)
        app = create_app(settings, modeldeck_transport=MockTransport(_unavailable_modeldeck))
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://speechshift.test") as client:
            payload = (await client.get("/api/config")).json()
        assert payload["provider"] == "replay"
        assert payload["provider_label"] == "Replay mode"
        assert payload["audio_sample_rate"] == 16_000
        assert payload["max_input_seconds"] == 8
        assert payload["visitor_idle_timeout_seconds"] == 120
        assert payload["local_voice_profiles"][-1] == {
            "id": "anonymised-voice",
            "label": "Anonymised voice",
            "description": "Experimental formant reshaping that keeps the recording's timing",
        }
        assert [provider["state"] for provider in payload["providers"]] == [
            "ready",
            "ready",
            "ready",
            "not-configured",
        ]

    asyncio.run(scenario())


def test_development_provider_selection_is_explicit() -> None:
    async def scenario() -> None:
        settings = Settings(replay_asset_dir=Path("assets/replay"), _env_file=None)
        app = create_app(settings, modeldeck_transport=MockTransport(_unavailable_modeldeck))
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://speechshift.test") as client:
            selected = await client.post(
                "/api/providers/select",
                json={"provider": "mock-modeldeck"},
            )
            rejected = await client.post(
                "/api/providers/select",
                json={"provider": "modeldeck"},
            )
        assert selected.status_code == 200
        assert selected.json()["provider"] == "mock-modeldeck"
        assert selected.json()["provider_label"] == "Mock contract"
        assert rejected.status_code == 409
        assert rejected.json()["detail"] == "provider is not ready"

    asyncio.run(scenario())


def test_modeldeck_can_only_be_selected_when_all_routes_are_ready() -> None:
    async def scenario() -> None:
        settings = Settings(replay_asset_dir=Path("assets/replay"), _env_file=None)
        app = create_app(settings, modeldeck_transport=MockTransport(_ready_modeldeck))
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://speechshift.test") as client:
            selected = await client.post(
                "/api/providers/select",
                json={"provider": "modeldeck"},
            )
        assert selected.status_code == 200
        payload = selected.json()
        assert payload["provider"] == "modeldeck"
        assert payload["providers"][-1]["state"] == "ready"
        assert [profile["id"] for profile in payload["modeldeck_voice_profiles"]] == [
            "ryan",
            "aiden",
            "vivian",
            "serena",
        ]
        assert payload["modeldeck_voice_profiles"][-2:] == [
            {
                "id": "vivian",
                "label": "Vivian",
                "description": "Bright built-in synthetic female voice",
            },
            {
                "id": "serena",
                "label": "Serena",
                "description": "Warm, gentle built-in synthetic female voice",
            },
        ]

    asyncio.run(scenario())
