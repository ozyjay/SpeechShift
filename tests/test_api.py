import asyncio
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from speechshift.config import Settings
from speechshift.main import create_app


def test_health_reports_replay_without_claiming_live_readiness() -> None:
    async def scenario() -> None:
        settings = Settings(replay_asset_dir=Path("assets/replay"), _env_file=None)
        transport = ASGITransport(app=create_app(settings))
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
        transport = ASGITransport(app=create_app(settings))
        async with AsyncClient(transport=transport, base_url="http://speechshift.test") as client:
            payload = (await client.get("/api/config")).json()
        assert payload["provider"] == "replay"
        assert payload["provider_label"] == "Replay mode"
        assert payload["audio_sample_rate"] == 16_000
        assert payload["max_input_seconds"] == 8
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
        transport = ASGITransport(app=create_app(settings))
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
