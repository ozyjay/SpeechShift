import asyncio

from speechshift.sessions import SessionStore


def test_clear_cancels_and_removes_session() -> None:
    async def scenario() -> None:
        store = SessionStore()
        session = await store.create()
        assert store.get(session.id) is session
        assert await store.clear(session.id) is True
        assert session.cancelled.is_set()
        assert store.get(session.id) is None
        assert await store.clear(session.id) is False

    asyncio.run(scenario())


def test_store_is_bounded() -> None:
    async def scenario() -> None:
        store = SessionStore(maximum_sessions=2)
        first = await store.create()
        await store.create()
        await store.create()
        assert first.cancelled.is_set()
        assert store.get(first.id) is None

    asyncio.run(scenario())

