"""Unit tests for SessionStore."""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import pytest
from pydantic_ai.messages import ModelMessage, ModelRequest, UserPromptPart

from sessions import SessionStore, Session, MAX_SESSIONS, MAX_HISTORY_MESSAGES


def create_mock_message(content: str = "test") -> ModelMessage:
    """Create a mock ModelMessage for testing."""
    return ModelRequest(parts=[UserPromptPart(content=content)])


class TestCreateSessionId:
    """Tests for create_session_id method."""

    def test_returns_valid_uuid_v4_format(self):
        """create_session_id should return a valid UUID v4 string."""
        store = SessionStore()
        session_id = store.create_session_id()

        # Should be a valid UUID
        parsed = uuid.UUID(session_id)
        assert str(parsed) == session_id

    def test_returns_uuid_version_4(self):
        """create_session_id should return specifically UUID version 4."""
        store = SessionStore()
        session_id = store.create_session_id()

        parsed = uuid.UUID(session_id)
        assert parsed.version == 4

    def test_returns_unique_ids(self):
        """Each call should return a unique session ID."""
        store = SessionStore()
        ids = {store.create_session_id() for _ in range(100)}

        assert len(ids) == 100

    def test_returns_lowercase_uuid(self):
        """Session ID should be lowercase."""
        store = SessionStore()
        session_id = store.create_session_id()

        assert session_id == session_id.lower()


class TestIsValidSessionId:
    """Tests for _is_valid_session_id method."""

    def test_valid_uuid_v4_accepted(self):
        """Valid UUID v4 should be accepted."""
        store = SessionStore()
        valid_id = "550e8400-e29b-41d4-a716-446655440000"

        assert store._is_valid_session_id(valid_id) is True

    def test_generated_session_id_is_valid(self):
        """Session IDs from create_session_id should be valid."""
        store = SessionStore()
        session_id = store.create_session_id()

        assert store._is_valid_session_id(session_id) is True

    def test_uppercase_uuid_v4_accepted(self):
        """Uppercase UUID v4 should be accepted (case insensitive)."""
        store = SessionStore()
        upper_id = "550E8400-E29B-41D4-A716-446655440000"

        assert store._is_valid_session_id(upper_id) is True

    def test_mixed_case_uuid_v4_accepted(self):
        """Mixed case UUID v4 should be accepted."""
        store = SessionStore()
        mixed_id = "550e8400-E29B-41d4-A716-446655440000"

        assert store._is_valid_session_id(mixed_id) is True

    def test_uuid_v1_rejected(self):
        """UUID v1 should be rejected (version digit must be 4)."""
        store = SessionStore()
        # UUID v1 has version 1 in the third group
        v1_id = "550e8400-e29b-11d4-a716-446655440000"

        assert store._is_valid_session_id(v1_id) is False

    def test_uuid_v3_rejected(self):
        """UUID v3 should be rejected."""
        store = SessionStore()
        v3_id = "550e8400-e29b-31d4-a716-446655440000"

        assert store._is_valid_session_id(v3_id) is False

    def test_uuid_v5_rejected(self):
        """UUID v5 should be rejected."""
        store = SessionStore()
        v5_id = "550e8400-e29b-51d4-a716-446655440000"

        assert store._is_valid_session_id(v5_id) is False

    def test_empty_string_rejected(self):
        """Empty string should be rejected."""
        store = SessionStore()

        assert store._is_valid_session_id("") is False

    def test_random_string_rejected(self):
        """Random non-UUID string should be rejected."""
        store = SessionStore()

        assert store._is_valid_session_id("not-a-uuid") is False

    def test_uuid_without_hyphens_rejected(self):
        """UUID without hyphens should be rejected."""
        store = SessionStore()
        no_hyphens = "550e8400e29b41d4a716446655440000"

        assert store._is_valid_session_id(no_hyphens) is False

    def test_uuid_with_extra_characters_rejected(self):
        """UUID with extra characters should be rejected."""
        store = SessionStore()
        extra = "550e8400-e29b-41d4-a716-446655440000-extra"

        assert store._is_valid_session_id(extra) is False

    def test_uuid_with_braces_rejected(self):
        """UUID with braces should be rejected."""
        store = SessionStore()
        braced = "{550e8400-e29b-41d4-a716-446655440000}"

        assert store._is_valid_session_id(braced) is False

    def test_short_uuid_rejected(self):
        """Truncated UUID should be rejected."""
        store = SessionStore()
        short = "550e8400-e29b-41d4-a716"

        assert store._is_valid_session_id(short) is False

    def test_invalid_variant_bits_rejected(self):
        """UUID with invalid variant bits (not 8, 9, a, or b) should be rejected."""
        store = SessionStore()
        # Fourth group must start with 8, 9, a, or b for variant 1
        invalid_variant = "550e8400-e29b-41d4-0716-446655440000"

        assert store._is_valid_session_id(invalid_variant) is False

    def test_none_type_raises_error(self):
        """None should raise an error (TypeError from regex)."""
        store = SessionStore()

        with pytest.raises(TypeError):
            store._is_valid_session_id(None)


class TestGetHistory:
    """Tests for get_history method."""

    @pytest.mark.asyncio
    async def test_new_session_returns_empty_list(self):
        """get_history for a non-existent session should return empty list."""
        store = SessionStore()
        session_id = store.create_session_id()

        history = await store.get_history(session_id)

        assert history == []

    @pytest.mark.asyncio
    async def test_invalid_session_id_returns_empty_list(self):
        """get_history with invalid session ID should return empty list."""
        store = SessionStore()

        history = await store.get_history("invalid-session-id")

        assert history == []

    @pytest.mark.asyncio
    async def test_returns_messages_after_update(self):
        """get_history should return messages after update_history is called."""
        store = SessionStore()
        session_id = store.create_session_id()
        messages = [create_mock_message("hello"), create_mock_message("world")]

        await store.update_history(session_id, messages)
        history = await store.get_history(session_id)

        assert len(history) == 2

    @pytest.mark.asyncio
    async def test_returns_copy_not_reference(self):
        """get_history should return a copy of messages, not a reference."""
        store = SessionStore()
        session_id = store.create_session_id()
        messages = [create_mock_message("test")]

        await store.update_history(session_id, messages)
        history1 = await store.get_history(session_id)
        history1.append(create_mock_message("modified"))
        history2 = await store.get_history(session_id)

        assert len(history2) == 1

    @pytest.mark.asyncio
    async def test_updates_last_accessed_time(self):
        """get_history should update the session's last_accessed timestamp."""
        store = SessionStore()
        session_id = store.create_session_id()
        messages = [create_mock_message("test")]

        await store.update_history(session_id, messages)
        initial_time = store._sessions[session_id].last_accessed

        await asyncio.sleep(0.01)
        await store.get_history(session_id)
        updated_time = store._sessions[session_id].last_accessed

        assert updated_time > initial_time


class TestUpdateHistory:
    """Tests for update_history method."""

    @pytest.mark.asyncio
    async def test_stores_messages(self):
        """update_history should store messages in the session."""
        store = SessionStore()
        session_id = store.create_session_id()
        messages = [create_mock_message("test message")]

        await store.update_history(session_id, messages)

        assert session_id in store._sessions
        assert len(store._sessions[session_id].messages) == 1

    @pytest.mark.asyncio
    async def test_invalid_session_id_ignored(self):
        """update_history with invalid session ID should be ignored."""
        store = SessionStore()

        await store.update_history("invalid-id", [create_mock_message("test")])

        assert len(store._sessions) == 0

    @pytest.mark.asyncio
    async def test_replaces_existing_messages(self):
        """update_history should replace existing messages, not append."""
        store = SessionStore()
        session_id = store.create_session_id()

        await store.update_history(session_id, [create_mock_message("first")])
        await store.update_history(session_id, [create_mock_message("second")])

        history = await store.get_history(session_id)
        assert len(history) == 1

    @pytest.mark.asyncio
    async def test_trims_to_max_history_messages(self):
        """update_history should trim messages to MAX_HISTORY_MESSAGES."""
        store = SessionStore()
        session_id = store.create_session_id()
        messages = [create_mock_message(f"msg-{i}") for i in range(MAX_HISTORY_MESSAGES + 50)]

        await store.update_history(session_id, messages)
        history = await store.get_history(session_id)

        assert len(history) == MAX_HISTORY_MESSAGES

    @pytest.mark.asyncio
    async def test_keeps_most_recent_messages_when_trimming(self):
        """When trimming, should keep the most recent (last) messages."""
        store = SessionStore()
        session_id = store.create_session_id()
        messages = [create_mock_message(f"msg-{i}") for i in range(MAX_HISTORY_MESSAGES + 10)]

        await store.update_history(session_id, messages)
        history = await store.get_history(session_id)

        # First message in trimmed history should be msg-10 (0-9 were trimmed)
        first_msg = history[0]
        assert isinstance(first_msg, ModelRequest)
        assert first_msg.parts[0].content == "msg-10"

    @pytest.mark.asyncio
    async def test_does_not_trim_under_max(self):
        """Messages under MAX_HISTORY_MESSAGES should not be trimmed."""
        store = SessionStore()
        session_id = store.create_session_id()
        messages = [create_mock_message(f"msg-{i}") for i in range(50)]

        await store.update_history(session_id, messages)
        history = await store.get_history(session_id)

        assert len(history) == 50

    @pytest.mark.asyncio
    async def test_updates_last_accessed_time(self):
        """update_history should set the session's last_accessed timestamp."""
        store = SessionStore()
        session_id = store.create_session_id()

        before = datetime.now(timezone.utc)
        await store.update_history(session_id, [create_mock_message("test")])
        after = datetime.now(timezone.utc)

        last_accessed = store._sessions[session_id].last_accessed
        assert before <= last_accessed <= after

    @pytest.mark.asyncio
    async def test_empty_messages_list_allowed(self):
        """update_history with empty list should create session with no messages."""
        store = SessionStore()
        session_id = store.create_session_id()

        await store.update_history(session_id, [])
        history = await store.get_history(session_id)

        assert history == []


class TestSessionEviction:
    """Tests for session eviction when MAX_SESSIONS is reached."""

    @pytest.mark.asyncio
    async def test_evicts_oldest_session_when_max_reached(self):
        """When MAX_SESSIONS is reached, oldest session should be evicted."""
        store = SessionStore()

        # Create sessions with controlled timestamps
        session_ids = []
        for i in range(MAX_SESSIONS):
            sid = store.create_session_id()
            session_ids.append(sid)
            await store.update_history(sid, [create_mock_message(f"session-{i}")])
            # Ensure unique timestamps
            store._sessions[sid].last_accessed = datetime.now(timezone.utc) + timedelta(seconds=i)

        oldest_session = session_ids[0]
        assert oldest_session in store._sessions

        # Add one more session
        new_session = store.create_session_id()
        await store.update_history(new_session, [create_mock_message("new")])

        # Oldest should be evicted
        assert oldest_session not in store._sessions
        assert new_session in store._sessions
        assert len(store._sessions) == MAX_SESSIONS

    @pytest.mark.asyncio
    async def test_no_eviction_under_max_sessions(self):
        """No eviction should occur when under MAX_SESSIONS."""
        store = SessionStore()

        session_ids = []
        for i in range(100):
            sid = store.create_session_id()
            session_ids.append(sid)
            await store.update_history(sid, [create_mock_message(f"session-{i}")])

        # All sessions should still exist
        for sid in session_ids:
            assert sid in store._sessions

    @pytest.mark.asyncio
    async def test_updating_existing_session_does_not_trigger_eviction(self):
        """Updating an existing session should not trigger eviction."""
        store = SessionStore()

        # Fill to max
        session_ids = []
        for i in range(MAX_SESSIONS):
            sid = store.create_session_id()
            session_ids.append(sid)
            await store.update_history(sid, [create_mock_message(f"session-{i}")])

        # Update existing session
        await store.update_history(session_ids[0], [create_mock_message("updated")])

        # No eviction should occur
        assert len(store._sessions) == MAX_SESSIONS
        for sid in session_ids:
            assert sid in store._sessions


class TestCleanupTaskLifecycle:
    """Tests for start_cleanup_task and stop_cleanup_task methods."""

    @pytest.mark.asyncio
    async def test_start_cleanup_task_creates_task(self):
        """start_cleanup_task should create a background task."""
        store = SessionStore()

        await store.start_cleanup_task()

        assert store._cleanup_task is not None
        assert not store._cleanup_task.done()

        await store.stop_cleanup_task()

    @pytest.mark.asyncio
    async def test_stop_cleanup_task_cancels_task(self):
        """stop_cleanup_task should cancel the background task."""
        store = SessionStore()

        await store.start_cleanup_task()
        await store.stop_cleanup_task()

        assert store._cleanup_task is None

    @pytest.mark.asyncio
    async def test_multiple_start_calls_do_not_create_multiple_tasks(self):
        """Multiple calls to start_cleanup_task should not create duplicate tasks."""
        store = SessionStore()

        await store.start_cleanup_task()
        first_task = store._cleanup_task
        await store.start_cleanup_task()
        second_task = store._cleanup_task

        assert first_task is second_task

        await store.stop_cleanup_task()

    @pytest.mark.asyncio
    async def test_stop_without_start_is_safe(self):
        """stop_cleanup_task should be safe to call without starting first."""
        store = SessionStore()

        await store.stop_cleanup_task()

        assert store._cleanup_task is None

    @pytest.mark.asyncio
    async def test_restart_after_stop(self):
        """Should be able to restart cleanup task after stopping."""
        store = SessionStore()

        await store.start_cleanup_task()
        await store.stop_cleanup_task()
        await store.start_cleanup_task()

        assert store._cleanup_task is not None
        assert not store._cleanup_task.done()

        await store.stop_cleanup_task()

    @pytest.mark.asyncio
    async def test_start_after_task_completes(self):
        """Should be able to start new task if previous task completed."""
        store = SessionStore()

        await store.start_cleanup_task()
        # Force task completion by cancelling
        store._cleanup_task.cancel()
        try:
            await store._cleanup_task
        except asyncio.CancelledError:
            pass

        # Task is done but not None
        assert store._cleanup_task.done()

        # Starting again should create new task
        await store.start_cleanup_task()
        assert not store._cleanup_task.done()

        await store.stop_cleanup_task()


class TestCleanupLoop:
    """Tests for the cleanup loop that expires sessions after TTL."""

    @pytest.mark.asyncio
    async def test_expired_sessions_are_removed(self):
        """Sessions older than TTL should be removed by cleanup."""
        store = SessionStore(ttl_minutes=1)
        session_id = store.create_session_id()
        await store.update_history(session_id, [create_mock_message("test")])

        # Manually set last_accessed to past TTL
        store._sessions[session_id].last_accessed = (
            datetime.now(timezone.utc) - timedelta(minutes=2)
        )

        # Manually trigger cleanup
        await store._cleanup_expired()

        assert session_id not in store._sessions

    @pytest.mark.asyncio
    async def test_non_expired_sessions_are_kept(self):
        """Sessions within TTL should not be removed by cleanup."""
        store = SessionStore(ttl_minutes=60)
        session_id = store.create_session_id()
        await store.update_history(session_id, [create_mock_message("test")])

        await store._cleanup_expired()

        assert session_id in store._sessions

    @pytest.mark.asyncio
    async def test_mixed_expiration(self):
        """Only expired sessions should be removed, keeping non-expired ones."""
        store = SessionStore(ttl_minutes=1)

        # Create expired session
        expired_id = store.create_session_id()
        await store.update_history(expired_id, [create_mock_message("expired")])
        store._sessions[expired_id].last_accessed = (
            datetime.now(timezone.utc) - timedelta(minutes=2)
        )

        # Create fresh session
        fresh_id = store.create_session_id()
        await store.update_history(fresh_id, [create_mock_message("fresh")])

        await store._cleanup_expired()

        assert expired_id not in store._sessions
        assert fresh_id in store._sessions

    @pytest.mark.asyncio
    async def test_cleanup_with_no_sessions(self):
        """Cleanup should handle empty session store gracefully."""
        store = SessionStore()

        # Should not raise
        await store._cleanup_expired()

        assert len(store._sessions) == 0

    @pytest.mark.asyncio
    async def test_ttl_is_configurable(self):
        """TTL should be configurable via constructor."""
        store = SessionStore(ttl_minutes=5)
        session_id = store.create_session_id()
        await store.update_history(session_id, [create_mock_message("test")])

        # Set to 4 minutes ago - should not expire
        store._sessions[session_id].last_accessed = (
            datetime.now(timezone.utc) - timedelta(minutes=4)
        )
        await store._cleanup_expired()
        assert session_id in store._sessions

        # Set to 6 minutes ago - should expire
        store._sessions[session_id].last_accessed = (
            datetime.now(timezone.utc) - timedelta(minutes=6)
        )
        await store._cleanup_expired()
        assert session_id not in store._sessions

    @pytest.mark.asyncio
    async def test_cleanup_loop_runs_periodically(self):
        """Cleanup loop should call _cleanup_expired periodically."""
        store = SessionStore()

        with patch.object(store, '_cleanup_expired') as mock_cleanup:
            with patch('sessions.CLEANUP_INTERVAL_SECONDS', 0.01):
                await store.start_cleanup_task()
                await asyncio.sleep(0.05)
                await store.stop_cleanup_task()

            assert mock_cleanup.call_count >= 1

    @pytest.mark.asyncio
    async def test_cleanup_loop_handles_exceptions(self):
        """Cleanup loop should continue running even if cleanup raises an exception."""
        store = SessionStore()
        call_count = 0

        async def failing_cleanup():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Test error")

        with patch.object(store, '_cleanup_expired', side_effect=failing_cleanup):
            with patch('sessions.CLEANUP_INTERVAL_SECONDS', 0.01):
                await store.start_cleanup_task()
                await asyncio.sleep(0.05)
                await store.stop_cleanup_task()

            # Should have been called multiple times despite first failure
            assert call_count >= 2


class TestSessionDataclass:
    """Tests for the Session dataclass."""

    def test_default_messages_is_empty_list(self):
        """Session should have empty messages list by default."""
        session = Session()

        assert session.messages == []

    def test_default_last_accessed_is_utc_now(self):
        """Session should have last_accessed set to current UTC time."""
        before = datetime.now(timezone.utc)
        session = Session()
        after = datetime.now(timezone.utc)

        assert before <= session.last_accessed <= after

    def test_messages_can_be_provided(self):
        """Session should accept messages in constructor."""
        messages = [create_mock_message("test")]
        session = Session(messages=messages)

        assert session.messages == messages

    def test_last_accessed_can_be_provided(self):
        """Session should accept last_accessed in constructor."""
        custom_time = datetime(2023, 1, 1, tzinfo=timezone.utc)
        session = Session(last_accessed=custom_time)

        assert session.last_accessed == custom_time

    def test_default_messages_are_independent(self):
        """Each Session instance should have independent default messages list."""
        session1 = Session()
        session2 = Session()
        session1.messages.append(create_mock_message("test"))

        assert len(session2.messages) == 0


class TestConcurrency:
    """Tests for concurrent access to SessionStore."""

    @pytest.mark.asyncio
    async def test_concurrent_updates_are_safe(self):
        """Concurrent updates to different sessions should be safe."""
        store = SessionStore()
        session_ids = [store.create_session_id() for _ in range(10)]

        async def update_session(sid: str, index: int):
            for i in range(10):
                await store.update_history(sid, [create_mock_message(f"{index}-{i}")])
                await asyncio.sleep(0.001)

        await asyncio.gather(*[
            update_session(sid, i) for i, sid in enumerate(session_ids)
        ])

        # All sessions should exist
        assert len(store._sessions) == 10

    @pytest.mark.asyncio
    async def test_concurrent_reads_and_writes(self):
        """Concurrent reads and writes should be safe."""
        store = SessionStore()
        session_id = store.create_session_id()
        await store.update_history(session_id, [create_mock_message("initial")])

        async def read_session():
            for _ in range(10):
                await store.get_history(session_id)
                await asyncio.sleep(0.001)

        async def write_session():
            for i in range(10):
                await store.update_history(session_id, [create_mock_message(f"msg-{i}")])
                await asyncio.sleep(0.001)

        await asyncio.gather(read_session(), write_session())

        # Session should still exist and be valid
        history = await store.get_history(session_id)
        assert len(history) >= 1
