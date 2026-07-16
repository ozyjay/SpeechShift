import asyncio
from pathlib import Path

from speechshift.models import ReplayRunRequest
from speechshift.replay import ReplayCatalogue, ReplayProvider
from speechshift.sessions import Session


def test_catalogue_meets_public_replay_minimum() -> None:
    catalogue = ReplayCatalogue(Path("assets/replay"))
    assert len(catalogue.data["sentences"]) >= 3
    for sentence in catalogue.data["sentences"]:
        assert len(sentence["voices"]) >= 3
        assert len(sentence["languages"]) >= 2


def test_replay_event_order_is_deterministic(monkeypatch) -> None:
    async def instant_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", instant_sleep)

    async def scenario() -> None:
        provider = ReplayProvider(ReplayCatalogue(Path("assets/replay")))
        session = Session(id="test-session")
        events: list[dict[str, object]] = []

        async def send(event: dict[str, object]) -> None:
            events.append(event)

        await provider.run(
            session,
            ReplayRunRequest(mode="language", sentence_id="campus", selection_id="fr"),
            send,
        )
        assert [event["type"] for event in events] == [
            "state",
            "audio",
            "transcript_final",
            "translation_final",
            "audio",
            "metrics",
            "complete",
        ]
        assert [event["sequence"] for event in events] == list(range(1, 8))

    asyncio.run(scenario())


def test_cancelled_replay_emits_nothing() -> None:
    async def scenario() -> None:
        provider = ReplayProvider(ReplayCatalogue(Path("assets/replay")))
        session = Session(id="cancelled")
        session.cancelled.set()
        events: list[dict[str, object]] = []
        await provider.run(
            session,
            ReplayRunRequest(mode="voice", sentence_id="campus", selection_id="robot"),
            events.append,
        )
        assert events == []

    asyncio.run(scenario())

