"""In-memory scan sessions with a TTL. Nothing is written to disk or a database."""
from __future__ import annotations

import asyncio
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

from .models import Report, ScanRequest


@dataclass
class Session:
    id: str
    request: ScanRequest
    report: Report
    created: float = field(default_factory=time.monotonic)
    events: list[dict[str, Any]] = field(default_factory=list)
    listeners: set[asyncio.Queue] = field(default_factory=set)
    raw: dict[str, Any] = field(default_factory=dict)   # raw values for matching; never serialised
    task: asyncio.Task | None = None

    def emit(self, event: dict[str, Any]) -> None:
        self.events.append(event)
        for q in list(self.listeners):
            q.put_nowait(event)


class SessionStore:
    def __init__(self, ttl_minutes: int):
        self.ttl = ttl_minutes * 60
        self._sessions: dict[str, Session] = {}

    def create(self, request: ScanRequest, report_factory) -> Session:
        self.sweep()
        sid = secrets.token_urlsafe(12)
        session = Session(id=sid, request=request, report=report_factory(sid))
        self._sessions[sid] = session
        return session

    def get(self, sid: str) -> Session | None:
        self.sweep()
        return self._sessions.get(sid)

    def delete(self, sid: str) -> bool:
        session = self._sessions.pop(sid, None)
        if session and session.task and not session.task.done():
            session.task.cancel()
        return session is not None

    def sweep(self) -> None:
        now = time.monotonic()
        for sid in [s.id for s in self._sessions.values() if now - s.created > self.ttl]:
            self.delete(sid)

    def __len__(self) -> int:
        return len(self._sessions)
