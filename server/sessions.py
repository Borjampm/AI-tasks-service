import asyncio
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pydantic_ai.messages import ModelMessage

logger = logging.getLogger(__name__)

CLEANUP_INTERVAL_SECONDS = 300
MAX_SESSIONS = 10000
MAX_HISTORY_MESSAGES = 100

UUID_PATTERN = re.compile(
    r'^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$',
    re.IGNORECASE
)


@dataclass
class Session:
    messages: list[ModelMessage] = field(default_factory=list)
    last_accessed: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SessionStore:
    def __init__(self, ttl_minutes: int = 60):
        self._sessions: dict[str, Session] = {}
        self._ttl = timedelta(minutes=ttl_minutes)
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task | None = None

    async def start_cleanup_task(self) -> None:
        async with self._lock:
            if self._cleanup_task is None or self._cleanup_task.done():
                self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop_cleanup_task(self) -> None:
        async with self._lock:
            if self._cleanup_task and not self._cleanup_task.done():
                self._cleanup_task.cancel()
                try:
                    await self._cleanup_task
                except asyncio.CancelledError:
                    pass
                self._cleanup_task = None

    async def _cleanup_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Session cleanup failed")

    async def _cleanup_expired(self) -> None:
        async with self._lock:
            now = datetime.now(timezone.utc)
            expired = [
                sid for sid, session in self._sessions.items()
                if now - session.last_accessed > self._ttl
            ]
            for sid in expired:
                del self._sessions[sid]

    def _is_valid_session_id(self, session_id: str) -> bool:
        return bool(UUID_PATTERN.match(session_id))

    def create_session_id(self) -> str:
        return str(uuid.uuid4())

    async def get_history(self, session_id: str) -> list[ModelMessage]:
        if not self._is_valid_session_id(session_id):
            return []

        async with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.last_accessed = datetime.now(timezone.utc)
                return session.messages.copy()
            return []

    async def update_history(self, session_id: str, messages: list[ModelMessage]) -> None:
        if not self._is_valid_session_id(session_id):
            return

        async with self._lock:
            if session_id not in self._sessions and len(self._sessions) >= MAX_SESSIONS:
                oldest_sid = min(
                    self._sessions,
                    key=lambda sid: self._sessions[sid].last_accessed
                )
                del self._sessions[oldest_sid]

            trimmed = messages[-MAX_HISTORY_MESSAGES:] if len(messages) > MAX_HISTORY_MESSAGES else messages
            self._sessions[session_id] = Session(
                messages=trimmed,
                last_accessed=datetime.now(timezone.utc)
            )


session_store = SessionStore()
