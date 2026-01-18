"""Session management with TTL-based cleanup and message history storage.

Provides in-memory session storage for conversational AI agents with automatic
cleanup of expired sessions. Sessions are identified by UUID v4 and track message
history along with last access times for TTL enforcement.

Module-level configuration:
    CLEANUP_INTERVAL_SECONDS: How often to run cleanup (default: 300s / 5 minutes)
    MAX_SESSIONS: Maximum concurrent sessions before evicting oldest (default: 10000)
    MAX_HISTORY_MESSAGES: Maximum messages stored per session (default: 100)

Typical usage:
    from server.sessions import session_store

    # Start cleanup background task
    await session_store.start_cleanup_task()

    # Create new session
    session_id = session_store.create_session_id()

    # Get message history
    history = await session_store.get_history(session_id)

    # Update with new messages
    await session_store.update_history(session_id, new_messages)

    # Cleanup on shutdown
    await session_store.stop_cleanup_task()
"""

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
    """Container for session message history and metadata.

    Attributes:
        messages: Conversation history as Pydantic AI ModelMessage objects.
        last_accessed: UTC timestamp of last access, used for TTL enforcement.
    """

    messages: list[ModelMessage] = field(default_factory=list)
    last_accessed: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SessionStore:
    """Thread-safe in-memory store for managing AI conversation sessions.

    Provides session lifecycle management with:
    - Automatic TTL-based expiration
    - Background cleanup task
    - Session capacity limits with LRU eviction
    - Message history trimming
    - UUID v4 validation

    Usage:
        store = SessionStore(ttl_minutes=30)
        await store.start_cleanup_task()

        # Create and use session
        session_id = store.create_session_id()
        await store.update_history(session_id, messages)
        history = await store.get_history(session_id)

        # Cleanup on shutdown
        await store.stop_cleanup_task()

    Attributes:
        _sessions: Internal session storage dictionary.
        _ttl: Time-to-live duration for sessions.
        _lock: Asyncio lock for thread-safe access.
        _cleanup_task: Background task handle for periodic cleanup.
    """

    def __init__(self, ttl_minutes: int = 60):
        """Initialize SessionStore with configurable TTL.

        Args:
            ttl_minutes: Session expiration time in minutes (default: 60).
        """
        self._sessions: dict[str, Session] = {}
        self._ttl = timedelta(minutes=ttl_minutes)
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task | None = None

    async def start_cleanup_task(self) -> None:
        """Start the background task for periodic session cleanup.

        Should be called during server initialization. Safe to call multiple times
        (will not create duplicate tasks). Cleanup runs every CLEANUP_INTERVAL_SECONDS.
        """
        async with self._lock:
            if self._cleanup_task is None or self._cleanup_task.done():
                self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop_cleanup_task(self) -> None:
        """Stop the background cleanup task gracefully.

        Should be called during server shutdown. Cancels the running task
        and waits for cancellation to complete. Safe to call even if no
        task is running.
        """
        async with self._lock:
            if self._cleanup_task and not self._cleanup_task.done():
                self._cleanup_task.cancel()
                try:
                    await self._cleanup_task
                except asyncio.CancelledError:
                    pass
                self._cleanup_task = None

    async def _cleanup_loop(self) -> None:
        """Internal background loop that runs periodic cleanup.

        Sleeps for CLEANUP_INTERVAL_SECONDS between cleanup runs.
        Logs exceptions but continues running. Exits cleanly on cancellation.
        """
        while True:
            try:
                await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Session cleanup failed")

    async def _cleanup_expired(self) -> None:
        """Remove sessions that have exceeded their TTL.

        Compares each session's last_accessed timestamp against current time.
        Deletes all sessions where (now - last_accessed) > TTL.
        """
        async with self._lock:
            now = datetime.now(timezone.utc)
            expired = [
                sid for sid, session in self._sessions.items()
                if now - session.last_accessed > self._ttl
            ]
            for sid in expired:
                del self._sessions[sid]

    def _is_valid_session_id(self, session_id: str) -> bool:
        """Validate session ID format against UUID v4 pattern.

        Args:
            session_id: Session identifier to validate.

        Returns:
            True if session_id matches UUID v4 format, False otherwise.
        """
        return bool(UUID_PATTERN.match(session_id))

    def create_session_id(self) -> str:
        """Generate a new UUID v4 session identifier.

        Returns:
            String representation of a new UUID v4.
        """
        return str(uuid.uuid4())

    async def get_history(self, session_id: str) -> list[ModelMessage]:
        """Retrieve message history for a session.

        Updates the session's last_accessed timestamp if found. Returns a copy
        of the message list to prevent external mutation.

        Args:
            session_id: UUID v4 session identifier.

        Returns:
            List of ModelMessage objects for the session. Empty list if session
            not found or session_id is invalid.
        """
        if not self._is_valid_session_id(session_id):
            return []

        async with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.last_accessed = datetime.now(timezone.utc)
                return session.messages.copy()
            return []

    async def update_history(self, session_id: str, messages: list[ModelMessage]) -> None:
        """Store or update message history for a session.

        Creates a new session if it doesn't exist. Enforces capacity limits by
        evicting the oldest session (by last_accessed) when MAX_SESSIONS is reached.
        Trims message history to MAX_HISTORY_MESSAGES, keeping the most recent.

        Args:
            session_id: UUID v4 session identifier.
            messages: Complete list of messages for the session.

        Note:
            Silently ignores invalid session IDs. Message list is trimmed to
            MAX_HISTORY_MESSAGES before storage (keeps most recent).
        """
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
