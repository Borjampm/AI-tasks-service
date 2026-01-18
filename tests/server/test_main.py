"""Unit tests for ChatServiceServicer and serve()."""

import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import grpc


# =============================================================================
# Helper classes for async mocking
# =============================================================================


class AsyncIterator:
    """Helper class to create async iterators for testing."""

    def __init__(self, items):
        self.items = items
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.items):
            raise StopAsyncIteration
        item = self.items[self.index]
        self.index += 1
        return item


class AsyncContextManager:
    """Helper class to create async context managers for testing."""

    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False


class MockChatRequest:
    """Mock ChatRequest for testing."""

    def __init__(self, message: str = "Hello", session_id: str = ""):
        self.message = message
        self.session_id = session_id


class MockChatResponse:
    """Mock ChatResponse for testing."""

    def __init__(self, message: str = "", session_id: str = ""):
        self.message = message
        self.session_id = session_id


# =============================================================================
# Tests for ChatServiceServicer.Chat() method
# =============================================================================


SERVER_PATH = Path(__file__).parent.parent.parent / "server"


class BaseChatServiceServicer:
    """Base class for ChatServiceServicer to avoid MagicMock inheritance issues."""
    pass


@pytest.fixture(autouse=True)
def cleanup_mocked_modules():
    """Clean up mocked modules after each test to prevent test pollution."""
    # Store original modules
    original_modules = {}
    modules_to_restore = [
        'chat_service_pb2',
        'chat_service_pb2_grpc',
        'logging_interceptor',
        'logfire',
        'agents',
        'sessions',
        'grpc_health.v1',
        'grpc_health.v1.health',
        'grpc_health.v1.health_pb2',
        'grpc_health.v1.health_pb2_grpc',
    ]

    for mod_name in modules_to_restore:
        if mod_name in sys.modules:
            original_modules[mod_name] = sys.modules[mod_name]

    yield

    # Restore original modules or remove mocked ones
    for mod_name in modules_to_restore:
        if mod_name in original_modules:
            sys.modules[mod_name] = original_modules[mod_name]
        elif mod_name in sys.modules:
            del sys.modules[mod_name]


def _load_main_with_mocks(mock_session_store, mock_chat_agent, module_name="main"):
    """Load main.py with mocked dependencies and return the module."""
    # Create mock grpc module with proper base class
    mock_chat_service_pb2_grpc = MagicMock()
    mock_chat_service_pb2_grpc.ChatServiceServicer = BaseChatServiceServicer

    mock_modules = {
        'chat_service_pb2': MagicMock(ChatResponse=MockChatResponse),
        'chat_service_pb2_grpc': mock_chat_service_pb2_grpc,
        'logging_interceptor': MagicMock(),
        'logfire': MagicMock(),
        'agents': MagicMock(chat_agent=mock_chat_agent),
        'sessions': MagicMock(session_store=mock_session_store),
        'grpc_health.v1': MagicMock(),
        'grpc_health.v1.health': MagicMock(),
        'grpc_health.v1.health_pb2': MagicMock(),
        'grpc_health.v1.health_pb2_grpc': MagicMock(),
    }

    # Apply patches
    for mod_name, mock_mod in mock_modules.items():
        sys.modules[mod_name] = mock_mod

    import importlib.util
    spec = importlib.util.spec_from_file_location(module_name, SERVER_PATH / "main.py")
    main_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(main_module)

    return main_module


class TestChatServiceServicerChat:
    """Tests for ChatServiceServicer.Chat() method."""

    @pytest.mark.asyncio
    async def test_creates_new_session_id_when_none_provided(self):
        """Chat() should create a new session_id when request has empty session_id."""
        # Create mocks inline
        mock_session_store = MagicMock()
        mock_session_store.create_session_id = MagicMock(return_value="test-session-123")
        mock_session_store.get_history = AsyncMock(return_value=[])
        mock_session_store.update_history = AsyncMock()

        mock_result = MagicMock()
        mock_result.stream_text = MagicMock(return_value=AsyncIterator(["Hello"]))
        mock_result.all_messages = MagicMock(return_value=[])

        mock_chat_agent = MagicMock()
        mock_chat_agent.run_stream = MagicMock(
            return_value=AsyncContextManager(mock_result)
        )

        main_module = _load_main_with_mocks(mock_session_store, mock_chat_agent, "main1")

        servicer = main_module.ChatServiceServicer()
        request = MockChatRequest(message="Hello", session_id="")
        context = MagicMock()

        responses = []
        async for response in servicer.Chat(request, context):
            responses.append(response)

        mock_session_store.create_session_id.assert_called_once()

    @pytest.mark.asyncio
    async def test_uses_existing_session_id_when_provided(self):
        """Chat() should use existing session_id when provided in request."""
        mock_session_store = MagicMock()
        mock_session_store.create_session_id = MagicMock(return_value="test-session-123")
        mock_session_store.get_history = AsyncMock(return_value=[])
        mock_session_store.update_history = AsyncMock()

        mock_result = MagicMock()
        mock_result.stream_text = MagicMock(return_value=AsyncIterator(["response"]))
        mock_result.all_messages = MagicMock(return_value=[])

        mock_chat_agent = MagicMock()
        mock_chat_agent.run_stream = MagicMock(
            return_value=AsyncContextManager(mock_result)
        )

        main_module = _load_main_with_mocks(mock_session_store, mock_chat_agent, "main2")

        servicer = main_module.ChatServiceServicer()
        request = MockChatRequest(message="Hello", session_id="existing-session-456")
        context = MagicMock()

        responses = []
        async for response in servicer.Chat(request, context):
            responses.append(response)

        mock_session_store.create_session_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_retrieves_message_history_from_session_store(self):
        """Chat() should retrieve message history from session_store."""
        existing_history = [MagicMock(), MagicMock()]

        mock_session_store = MagicMock()
        mock_session_store.create_session_id = MagicMock(return_value="test-session-123")
        mock_session_store.get_history = AsyncMock(return_value=existing_history)
        mock_session_store.update_history = AsyncMock()

        mock_result = MagicMock()
        mock_result.stream_text = MagicMock(return_value=AsyncIterator(["response"]))
        mock_result.all_messages = MagicMock(return_value=[])

        mock_chat_agent = MagicMock()
        mock_chat_agent.run_stream = MagicMock(
            return_value=AsyncContextManager(mock_result)
        )

        main_module = _load_main_with_mocks(mock_session_store, mock_chat_agent, "main3")

        servicer = main_module.ChatServiceServicer()
        request = MockChatRequest(message="Hello", session_id="")
        context = MagicMock()

        async for _ in servicer.Chat(request, context):
            pass

        mock_session_store.get_history.assert_called_once_with("test-session-123")
        mock_chat_agent.run_stream.assert_called_once_with(
            "Hello",
            message_history=existing_history
        )

    @pytest.mark.asyncio
    async def test_streams_responses_from_chat_agent(self):
        """Chat() should stream responses from chat_agent."""
        mock_session_store = MagicMock()
        mock_session_store.create_session_id = MagicMock(return_value="test-session-123")
        mock_session_store.get_history = AsyncMock(return_value=[])
        mock_session_store.update_history = AsyncMock()

        mock_result = MagicMock()
        mock_result.stream_text = MagicMock(
            return_value=AsyncIterator(["chunk1", "chunk2", "chunk3"])
        )
        mock_result.all_messages = MagicMock(return_value=[])

        mock_chat_agent = MagicMock()
        mock_chat_agent.run_stream = MagicMock(
            return_value=AsyncContextManager(mock_result)
        )

        main_module = _load_main_with_mocks(mock_session_store, mock_chat_agent, "main4")

        servicer = main_module.ChatServiceServicer()
        request = MockChatRequest(message="Hello", session_id="")
        context = MagicMock()

        responses = []
        async for response in servicer.Chat(request, context):
            responses.append(response)

        assert len(responses) == 3

    @pytest.mark.asyncio
    async def test_strips_trailing_newline_from_final_chunk(self):
        """Chat() should strip trailing newline from the final chunk."""
        mock_session_store = MagicMock()
        mock_session_store.create_session_id = MagicMock(return_value="test-session-123")
        mock_session_store.get_history = AsyncMock(return_value=[])
        mock_session_store.update_history = AsyncMock()

        mock_result = MagicMock()
        mock_result.stream_text = MagicMock(return_value=AsyncIterator(["Hello\n"]))
        mock_result.all_messages = MagicMock(return_value=[])

        mock_chat_agent = MagicMock()
        mock_chat_agent.run_stream = MagicMock(
            return_value=AsyncContextManager(mock_result)
        )

        main_module = _load_main_with_mocks(mock_session_store, mock_chat_agent, "main5")

        servicer = main_module.ChatServiceServicer()
        request = MockChatRequest(message="Hello", session_id="")
        context = MagicMock()

        responses = []
        async for response in servicer.Chat(request, context):
            responses.append(response)

        assert len(responses) == 1
        assert responses[0].message == "Hello"
        assert not responses[0].message.endswith("\n")

    @pytest.mark.asyncio
    async def test_updates_session_history_after_successful_response(self):
        """Chat() should update session history after successful response."""
        new_messages = [MagicMock(), MagicMock()]

        mock_session_store = MagicMock()
        mock_session_store.create_session_id = MagicMock(return_value="test-session-123")
        mock_session_store.get_history = AsyncMock(return_value=[])
        mock_session_store.update_history = AsyncMock()

        mock_result = MagicMock()
        mock_result.stream_text = MagicMock(return_value=AsyncIterator(["response"]))
        mock_result.all_messages = MagicMock(return_value=new_messages)

        mock_chat_agent = MagicMock()
        mock_chat_agent.run_stream = MagicMock(
            return_value=AsyncContextManager(mock_result)
        )

        main_module = _load_main_with_mocks(mock_session_store, mock_chat_agent, "main6")

        servicer = main_module.ChatServiceServicer()
        request = MockChatRequest(message="Hello", session_id="")
        context = MagicMock()

        async for _ in servicer.Chat(request, context):
            pass

        mock_session_store.update_history.assert_called_once_with(
            "test-session-123", new_messages
        )

    @pytest.mark.asyncio
    async def test_sets_internal_error_code_on_exception(self):
        """Chat() should set INTERNAL error code on exception."""
        mock_session_store = MagicMock()
        mock_session_store.create_session_id = MagicMock(return_value="test-session-123")
        mock_session_store.get_history = AsyncMock(
            side_effect=RuntimeError("Database error")
        )

        mock_chat_agent = MagicMock()

        main_module = _load_main_with_mocks(mock_session_store, mock_chat_agent, "main7")

        servicer = main_module.ChatServiceServicer()
        request = MockChatRequest(message="Hello", session_id="")
        context = MagicMock()

        with pytest.raises(RuntimeError):
            async for _ in servicer.Chat(request, context):
                pass

        context.set_code.assert_called_once_with(grpc.StatusCode.INTERNAL)
        context.set_details.assert_called_once_with("An internal error occurred")

    @pytest.mark.asyncio
    async def test_logs_exceptions_properly(self):
        """Chat() should log exceptions properly."""
        mock_session_store = MagicMock()
        mock_session_store.create_session_id = MagicMock(return_value="test-session-123")
        mock_session_store.get_history = AsyncMock(
            side_effect=RuntimeError("Test error")
        )

        mock_chat_agent = MagicMock()

        main_module = _load_main_with_mocks(mock_session_store, mock_chat_agent, "main8")

        mock_logger = MagicMock()
        main_module.logger = mock_logger

        servicer = main_module.ChatServiceServicer()
        request = MockChatRequest(message="Hello", session_id="")
        context = MagicMock()

        with pytest.raises(RuntimeError):
            async for _ in servicer.Chat(request, context):
                pass

        mock_logger.exception.assert_called_once_with("Chat request failed")
