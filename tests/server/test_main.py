"""Unit tests for ChatServiceServicer and serve()."""

import pytest
import sys
import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
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


@pytest.fixture(autouse=True)
def setup_server_path():
    """Ensure server path is at the front of sys.path."""
    server_path_str = str(SERVER_PATH)
    if server_path_str not in sys.path:
        sys.path.insert(0, server_path_str)
    yield


def create_mocked_server_main(
    session_store_config: dict = None,
    chat_agent_config: dict = None,
):
    """
    Create a fresh server main module with all dependencies mocked.

    Args:
        session_store_config: Dict with keys like 'create_session_id', 'get_history', 'update_history'
        chat_agent_config: Dict with keys like 'run_stream'

    Returns:
        Dict with 'module', 'chat_service_pb2', 'session_store', 'chat_agent'
    """
    session_store_config = session_store_config or {}
    chat_agent_config = chat_agent_config or {}

    # Create mock modules that would be imported by main.py
    mock_chat_service_pb2 = MagicMock()
    mock_chat_service_pb2.ChatResponse = MockChatResponse
    mock_chat_service_pb2.ChatRequest = MockChatRequest

    mock_chat_service_pb2_grpc = MagicMock()

    mock_logging_interceptor = MagicMock()
    mock_logging_interceptor.LoggingInterceptor = MagicMock()
    mock_logging_interceptor.setup_logging = MagicMock()

    mock_logfire = MagicMock()

    # Create persistent mock objects for session_store and chat_agent
    # Configure them BEFORE loading the module
    mock_session_store = MagicMock()
    if 'create_session_id' in session_store_config:
        mock_session_store.create_session_id.return_value = session_store_config['create_session_id']
    if 'get_history' in session_store_config:
        mock_session_store.get_history = session_store_config['get_history']
    if 'update_history' in session_store_config:
        mock_session_store.update_history = session_store_config['update_history']

    mock_chat_agent = MagicMock()
    if 'run_stream' in chat_agent_config:
        mock_chat_agent.run_stream = chat_agent_config['run_stream']

    mock_agents = MagicMock()
    mock_agents.chat_agent = mock_chat_agent

    mock_sessions = MagicMock()
    mock_sessions.session_store = mock_session_store

    mock_health = MagicMock()
    mock_health_pb2 = MagicMock()
    mock_health_pb2_grpc = MagicMock()

    # Store original modules to restore later
    original_modules = {}
    modules_to_mock = {
        "chat_service_pb2": mock_chat_service_pb2,
        "chat_service_pb2_grpc": mock_chat_service_pb2_grpc,
        "logging_interceptor": mock_logging_interceptor,
        "logfire": mock_logfire,
        "agents": mock_agents,
        "sessions": mock_sessions,
        "grpc_health.v1.health": mock_health,
        "grpc_health.v1.health_pb2": mock_health_pb2,
        "grpc_health.v1.health_pb2_grpc": mock_health_pb2_grpc,
        "grpc_health.v1": MagicMock(),
        "grpc_health": MagicMock(),
    }

    for mod_name in modules_to_mock:
        if mod_name in sys.modules:
            original_modules[mod_name] = sys.modules[mod_name]
        sys.modules[mod_name] = modules_to_mock[mod_name]

    # Load the server main module
    spec = importlib.util.spec_from_file_location(
        "server_main",
        SERVER_PATH / "main.py"
    )
    server_main = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server_main)

    return {
        "module": server_main,
        "chat_service_pb2": mock_chat_service_pb2,
        "session_store": mock_session_store,
        "chat_agent": mock_chat_agent,
        "original_modules": original_modules,
        "modules_to_mock": modules_to_mock,
    }


def cleanup_mocked_modules(mocked_result: dict):
    """Clean up mocked modules after test."""
    original_modules = mocked_result["original_modules"]
    modules_to_mock = mocked_result["modules_to_mock"]

    for mod_name in modules_to_mock:
        if mod_name in original_modules:
            sys.modules[mod_name] = original_modules[mod_name]
        elif mod_name in sys.modules:
            del sys.modules[mod_name]


class TestChatServiceServicerChat:
    """Tests for ChatServiceServicer.Chat() method."""

    @pytest.mark.asyncio
    async def test_creates_new_session_id_when_none_provided(self):
        """Chat() should create a new session_id when request has empty session_id."""
        mock_result = MagicMock()
        mock_result.stream_text = MagicMock(return_value=AsyncIterator(["Hello"]))
        mock_result.all_messages = MagicMock(return_value=[])

        mocked = create_mocked_server_main(
            session_store_config={
                'create_session_id': "new-session-123",
                'get_history': AsyncMock(return_value=[]),
                'update_history': AsyncMock(),
            },
            chat_agent_config={
                'run_stream': MagicMock(return_value=AsyncContextManager(mock_result)),
            }
        )

        try:
            server_main = mocked["module"]
            mock_session_store = mocked["session_store"]

            servicer = server_main.ChatServiceServicer()
            request = MockChatRequest(message="Hello", session_id="")
            context = MagicMock()

            responses = []
            async for response in servicer.Chat(request, context):
                responses.append(response)

            mock_session_store.create_session_id.assert_called_once()
        finally:
            cleanup_mocked_modules(mocked)

    @pytest.mark.asyncio
    async def test_uses_existing_session_id_when_provided(self):
        """Chat() should use existing session_id when provided in request."""
        mock_result = MagicMock()
        mock_result.stream_text = MagicMock(return_value=AsyncIterator(["response"]))
        mock_result.all_messages = MagicMock(return_value=[])

        mocked = create_mocked_server_main(
            session_store_config={
                'create_session_id': "should-not-be-used",
                'get_history': AsyncMock(return_value=[]),
                'update_history': AsyncMock(),
            },
            chat_agent_config={
                'run_stream': MagicMock(return_value=AsyncContextManager(mock_result)),
            }
        )

        try:
            server_main = mocked["module"]
            mock_session_store = mocked["session_store"]

            servicer = server_main.ChatServiceServicer()
            request = MockChatRequest(message="Hello", session_id="existing-session-456")
            context = MagicMock()

            responses = []
            async for response in servicer.Chat(request, context):
                responses.append(response)

            mock_session_store.create_session_id.assert_not_called()
        finally:
            cleanup_mocked_modules(mocked)

    @pytest.mark.asyncio
    async def test_retrieves_message_history_from_session_store(self):
        """Chat() should retrieve message history from session_store."""
        existing_history = [MagicMock(), MagicMock()]

        mock_result = MagicMock()
        mock_result.stream_text = MagicMock(return_value=AsyncIterator(["response"]))
        mock_result.all_messages = MagicMock(return_value=[])

        mocked = create_mocked_server_main(
            session_store_config={
                'create_session_id': "session-123",
                'get_history': AsyncMock(return_value=existing_history),
                'update_history': AsyncMock(),
            },
            chat_agent_config={
                'run_stream': MagicMock(return_value=AsyncContextManager(mock_result)),
            }
        )

        try:
            server_main = mocked["module"]
            mock_session_store = mocked["session_store"]
            mock_chat_agent = mocked["chat_agent"]

            servicer = server_main.ChatServiceServicer()
            request = MockChatRequest(message="Hello", session_id="")
            context = MagicMock()

            async for _ in servicer.Chat(request, context):
                pass

            mock_session_store.get_history.assert_called_once_with("session-123")
            mock_chat_agent.run_stream.assert_called_once_with(
                "Hello",
                message_history=existing_history
            )
        finally:
            cleanup_mocked_modules(mocked)

    @pytest.mark.asyncio
    async def test_streams_responses_from_chat_agent(self):
        """Chat() should stream responses from chat_agent."""
        mock_result = MagicMock()
        mock_result.stream_text = MagicMock(return_value=AsyncIterator(["chunk1", "chunk2", "chunk3"]))
        mock_result.all_messages = MagicMock(return_value=[])

        mocked = create_mocked_server_main(
            session_store_config={
                'create_session_id': "session-123",
                'get_history': AsyncMock(return_value=[]),
                'update_history': AsyncMock(),
            },
            chat_agent_config={
                'run_stream': MagicMock(return_value=AsyncContextManager(mock_result)),
            }
        )

        try:
            server_main = mocked["module"]

            servicer = server_main.ChatServiceServicer()
            request = MockChatRequest(message="Hello", session_id="")
            context = MagicMock()

            responses = []
            async for response in servicer.Chat(request, context):
                responses.append(response)

            assert len(responses) == 3
        finally:
            cleanup_mocked_modules(mocked)

    @pytest.mark.asyncio
    async def test_strips_trailing_newline_from_final_chunk(self):
        """Chat() should strip trailing newline from the final chunk."""
        mock_result = MagicMock()
        mock_result.stream_text = MagicMock(return_value=AsyncIterator(["Hello\n"]))
        mock_result.all_messages = MagicMock(return_value=[])

        mocked = create_mocked_server_main(
            session_store_config={
                'create_session_id': "session-123",
                'get_history': AsyncMock(return_value=[]),
                'update_history': AsyncMock(),
            },
            chat_agent_config={
                'run_stream': MagicMock(return_value=AsyncContextManager(mock_result)),
            }
        )

        try:
            server_main = mocked["module"]

            servicer = server_main.ChatServiceServicer()
            request = MockChatRequest(message="Hello", session_id="")
            context = MagicMock()

            responses = []
            async for response in servicer.Chat(request, context):
                responses.append(response)

            assert len(responses) == 1
            assert responses[0].message == "Hello"
            assert not responses[0].message.endswith("\n")
        finally:
            cleanup_mocked_modules(mocked)

    @pytest.mark.asyncio
    async def test_updates_session_history_after_successful_response(self):
        """Chat() should update session history after successful response."""
        new_messages = [MagicMock(), MagicMock()]

        mock_result = MagicMock()
        mock_result.stream_text = MagicMock(return_value=AsyncIterator(["response"]))
        mock_result.all_messages = MagicMock(return_value=new_messages)

        update_history_mock = AsyncMock()

        mocked = create_mocked_server_main(
            session_store_config={
                'create_session_id': "session-123",
                'get_history': AsyncMock(return_value=[]),
                'update_history': update_history_mock,
            },
            chat_agent_config={
                'run_stream': MagicMock(return_value=AsyncContextManager(mock_result)),
            }
        )

        try:
            server_main = mocked["module"]

            servicer = server_main.ChatServiceServicer()
            request = MockChatRequest(message="Hello", session_id="")
            context = MagicMock()

            async for _ in servicer.Chat(request, context):
                pass

            update_history_mock.assert_called_once_with("session-123", new_messages)
        finally:
            cleanup_mocked_modules(mocked)

    @pytest.mark.asyncio
    async def test_sets_internal_error_code_on_exception(self):
        """Chat() should set INTERNAL error code on exception."""
        mocked = create_mocked_server_main(
            session_store_config={
                'create_session_id': "session-123",
                'get_history': AsyncMock(side_effect=RuntimeError("Database error")),
            },
        )

        try:
            server_main = mocked["module"]

            servicer = server_main.ChatServiceServicer()
            request = MockChatRequest(message="Hello", session_id="")
            context = MagicMock()

            with pytest.raises(RuntimeError):
                async for _ in servicer.Chat(request, context):
                    pass

            context.set_code.assert_called_once_with(grpc.StatusCode.INTERNAL)
            context.set_details.assert_called_once_with("An internal error occurred")
        finally:
            cleanup_mocked_modules(mocked)

    @pytest.mark.asyncio
    async def test_logs_exceptions_properly(self):
        """Chat() should log exceptions properly."""
        mocked = create_mocked_server_main(
            session_store_config={
                'create_session_id': "session-123",
                'get_history': AsyncMock(side_effect=RuntimeError("Test error")),
            },
        )

        try:
            server_main = mocked["module"]
            mock_logger = MagicMock()
            server_main.logger = mock_logger

            servicer = server_main.ChatServiceServicer()
            request = MockChatRequest(message="Hello", session_id="")
            context = MagicMock()

            with pytest.raises(RuntimeError):
                async for _ in servicer.Chat(request, context):
                    pass

            mock_logger.exception.assert_called_once_with("Chat request failed")
        finally:
            cleanup_mocked_modules(mocked)
