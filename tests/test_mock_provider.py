import asyncio
from pathlib import Path

from speechshift.mock_provider import MockSpeechProvider
from speechshift.models import MockRunRequest
from speechshift.replay import ReplayCatalogue
from speechshift.sessions import Session


def test_mock_provider_streams_deterministic_fixture_as_binary(monkeypatch) -> None:
    async def instant_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", instant_sleep)

    async def scenario() -> None:
        provider = MockSpeechProvider(ReplayCatalogue(Path("assets/replay")))
        events: list[dict[str, object]] = []
        frames: list[bytes] = []

        async def send_json(event: dict[str, object]) -> None:
            events.append(event)

        async def send_bytes(frame: bytes) -> None:
            frames.append(frame)

        await provider.run(
            Session(id="mock-session"),
            MockRunRequest(
                mode="language",
                sentence_id="campus",
                selection_id="fr",
                audio_format={"encoding": "pcm_s16le", "sample_rate_hz": 16_000, "channels": 1},
            ),
            input_pcm=b"\x00\x00" * 16_000,
            input_frames=50,
            send_json=send_json,
            send_bytes=send_bytes,
        )
        assert [event["type"] for event in events] == [
            "state",
            "transcript_partial",
            "transcript_final",
            "translation_final",
            "audio_start",
            "audio_end",
            "metrics",
            "complete",
        ]
        assert all(event["mock"] is True for event in events)
        assert frames
        assert [int.from_bytes(frame[:4], "little") for frame in frames] == list(
            range(1, len(frames) + 1)
        )
        assert events[-2]["input_audio_ms"] == 1_000
        assert events[-2]["input_frames"] == 50

    asyncio.run(scenario())

