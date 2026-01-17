"""Server-specific test fixtures."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def mock_chat_agent():
    """Create a mock chat_agent for testing."""
    agent = MagicMock()
    return agent


@pytest.fixture
def mock_session_store():
    """Create a mock session_store for testing."""
    store = MagicMock()
    store.create_session_id = MagicMock(return_value="test-session-id")
    store.get_history = AsyncMock(return_value=[])
    store.update_history = AsyncMock()
    return store


@pytest.fixture
def mock_grpc_context():
    """Create a mock gRPC context for testing."""
    context = MagicMock()
    context.set_code = MagicMock()
    context.set_details = MagicMock()
    return context
