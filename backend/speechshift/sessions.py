from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from uuid import uuid4


@dataclass(slots=True)
class Session:
    id: str
    generation: int = 1
    sequence: int = 0
    cancelled: asyncio.Event = field(default_factory=asyncio.Event)

    def next_sequence(self) -> int:
        self.sequence += 1
        return self.sequence

    def reset(self) -> None:
        self.cancelled.set()
        self.generation += 1
        self.sequence = 0


class SessionStore:
    def __init__(self, maximum_sessions: int = 32) -> None:
        self._sessions: dict[str, Session] = {}
        self._maximum_sessions = maximum_sessions
        self._lock = asyncio.Lock()

    async def create(self) -> Session:
        async with self._lock:
            if len(self._sessions) >= self._maximum_sessions:
                oldest_id = next(iter(self._sessions))
                self._sessions.pop(oldest_id).reset()
            session = Session(id=uuid4().hex)
            self._sessions[session.id] = session
            return session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    async def clear(self, session_id: str) -> bool:
        async with self._lock:
            session = self._sessions.pop(session_id, None)
            if session is None:
                return False
            session.reset()
            return True

    async def clear_all(self) -> None:
        async with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            session.reset()

