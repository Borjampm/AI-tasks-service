"""Database-specific test fixtures."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from contextlib import asynccontextmanager

from database.manager import DatabaseManager


@pytest.fixture(autouse=True)
async def reset_singleton():
    """Reset DatabaseManager singleton before and after each test."""
    DatabaseManager._instance = None
    yield
    if DatabaseManager._instance is not None:
        try:
            await DatabaseManager._instance.close()
        except Exception:
            pass
        DatabaseManager._instance = None


@pytest.fixture
def mock_db_manager():
    """Create a mock DatabaseManager."""
    manager = MagicMock(spec=DatabaseManager)
    return manager


@pytest.fixture
def mock_connection():
    """Create a mock database connection."""
    conn = AsyncMock()
    return conn


@pytest.fixture
def mock_db_with_connection(mock_db_manager, mock_connection):
    """Create a mock DatabaseManager with connection context manager."""
    @asynccontextmanager
    async def mock_connection_cm():
        yield mock_connection

    mock_db_manager.connection = mock_connection_cm
    return mock_db_manager
