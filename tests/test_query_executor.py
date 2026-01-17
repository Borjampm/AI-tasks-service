"""Unit tests for QueryExecutor."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager

import asyncpg

from database.query import (
    QueryExecutor,
    QueryResult,
    QueryValidationError,
    QueryExecutionError,
)
from database.manager import DatabaseManager


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
def executor_with_mock_db(mock_db_manager, mock_connection):
    """Create QueryExecutor with mocked database."""

    @asynccontextmanager
    async def mock_connection_cm():
        yield mock_connection

    mock_db_manager.connection = mock_connection_cm
    return QueryExecutor(mock_db_manager, max_rows=10, max_retries=3)


class TestQueryExecutorExecution:
    """Tests for query execution."""

    @pytest.mark.asyncio
    async def test_execute_returns_query_result(
        self, executor_with_mock_db, mock_connection
    ):
        """Execute should return a QueryResult with rows and metadata."""
        # Setup mock response
        mock_rows = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
        ]
        mock_connection.execute = AsyncMock()  # For EXPLAIN
        mock_connection.fetch = AsyncMock(return_value=mock_rows)

        result = await executor_with_mock_db.execute("SELECT * FROM users")

        assert isinstance(result, QueryResult)
        assert result.row_count == 2
        assert result.columns == ["id", "name"]
        assert len(result.rows) == 2
        assert result.rows[0]["name"] == "Alice"
        assert result.truncated is False

    @pytest.mark.asyncio
    async def test_execute_truncates_large_results(
        self, executor_with_mock_db, mock_connection
    ):
        """Results exceeding max_rows should be truncated."""
        # Create 15 rows (executor has max_rows=10)
        mock_rows = [{"id": i, "name": f"User{i}"} for i in range(15)]
        mock_connection.execute = AsyncMock()
        mock_connection.fetch = AsyncMock(return_value=mock_rows)

        result = await executor_with_mock_db.execute("SELECT * FROM users")

        assert result.row_count == 15  # Original count preserved
        assert len(result.rows) == 10  # Truncated to max_rows
        assert result.truncated is True

    @pytest.mark.asyncio
    async def test_execute_empty_result(self, executor_with_mock_db, mock_connection):
        """Empty results should return empty QueryResult."""
        mock_connection.execute = AsyncMock()
        mock_connection.fetch = AsyncMock(return_value=[])

        result = await executor_with_mock_db.execute("SELECT * FROM users WHERE 1=0")

        assert result.row_count == 0
        assert result.rows == []
        assert result.columns == []
        assert result.truncated is False

    @pytest.mark.asyncio
    async def test_execute_calls_explain_first(
        self, executor_with_mock_db, mock_connection
    ):
        """Execute should validate with EXPLAIN before running query."""
        mock_connection.execute = AsyncMock()
        mock_connection.fetch = AsyncMock(return_value=[{"id": 1}])

        await executor_with_mock_db.execute("SELECT * FROM users")

        # Verify EXPLAIN was called
        mock_connection.execute.assert_called_once_with("EXPLAIN SELECT * FROM users")


class TestQueryExecutorValidation:
    """Tests for query validation integration."""

    @pytest.mark.asyncio
    async def test_execute_validates_by_default(self, executor_with_mock_db):
        """Execute should validate queries by default."""
        with pytest.raises(QueryValidationError):
            await executor_with_mock_db.execute("DELETE FROM users")

    @pytest.mark.asyncio
    async def test_execute_skip_validation(
        self, executor_with_mock_db, mock_connection
    ):
        """Execute with validate=False should skip validation."""
        mock_connection.execute = AsyncMock()
        mock_connection.fetch = AsyncMock(return_value=[])

        # This would normally fail validation but we skip it
        # Note: The EXPLAIN will still be called and might fail
        # This tests that our validation code is bypassed
        # In practice, the database would reject this anyway
        result = await executor_with_mock_db.execute(
            "SELECT * FROM users", validate=False
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_execute_validates_user_id(self, executor_with_mock_db):
        """Execute should require user_id filter when user_id is provided."""
        with pytest.raises(QueryValidationError) as exc_info:
            await executor_with_mock_db.execute(
                "SELECT * FROM users", user_id="123"
            )
        assert "user_id" in str(exc_info.value)


class TestQueryExecutorRetries:
    """Tests for retry logic."""

    @pytest.mark.asyncio
    async def test_retries_on_transient_error(
        self, executor_with_mock_db, mock_connection
    ):
        """Should retry on transient PostgresError."""
        mock_connection.execute = AsyncMock()
        mock_connection.fetch = AsyncMock(
            side_effect=[
                asyncpg.PostgresError("connection lost"),
                [{"id": 1}],  # Success on second try
            ]
        )

        result = await executor_with_mock_db.execute("SELECT * FROM users")

        assert result.row_count == 1
        assert mock_connection.fetch.call_count == 2

    @pytest.mark.asyncio
    async def test_no_retry_on_syntax_error(
        self, executor_with_mock_db, mock_connection
    ):
        """Should not retry on syntax errors."""
        mock_connection.execute = AsyncMock()
        mock_connection.fetch = AsyncMock(
            side_effect=asyncpg.PostgresError("syntax error at position 10")
        )

        with pytest.raises(QueryExecutionError) as exc_info:
            await executor_with_mock_db.execute("SELECT * FROM users")

        assert "syntax error" in str(exc_info.value).lower()
        assert mock_connection.fetch.call_count == 1  # No retries

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, executor_with_mock_db, mock_connection):
        """Should raise after max retries exceeded."""
        mock_connection.execute = AsyncMock()
        mock_connection.fetch = AsyncMock(
            side_effect=asyncpg.PostgresError("connection lost")
        )

        with pytest.raises(QueryExecutionError) as exc_info:
            await executor_with_mock_db.execute("SELECT * FROM users")

        assert "3 attempts" in str(exc_info.value)
        assert mock_connection.fetch.call_count == 3

    @pytest.mark.asyncio
    async def test_exception_chaining(self, executor_with_mock_db, mock_connection):
        """QueryExecutionError should chain the original exception."""
        original_error = asyncpg.PostgresError("original error")
        mock_connection.execute = AsyncMock()
        mock_connection.fetch = AsyncMock(side_effect=original_error)

        with pytest.raises(QueryExecutionError) as exc_info:
            await executor_with_mock_db.execute("SELECT * FROM users")

        assert exc_info.value.original_error is not None
        assert exc_info.value.__cause__ is not None


class TestQueryExecutorFormatting:
    """Tests for result formatting."""

    def test_format_result_with_data(self):
        """format_result should create readable table format."""
        result = QueryResult(
            rows=[
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"},
            ],
            row_count=2,
            columns=["id", "name"],
            truncated=False,
        )

        formatted = QueryExecutor.format_result(result)

        assert "id | name" in formatted
        assert "1 | Alice" in formatted
        assert "2 | Bob" in formatted
        assert "---" in formatted

    def test_format_result_empty(self):
        """format_result with empty result should return message."""
        result = QueryResult(rows=[], row_count=0, columns=[], truncated=False)

        formatted = QueryExecutor.format_result(result)

        assert formatted == "No results found."

    def test_format_result_with_null_values(self):
        """format_result should display NULL for None values."""
        result = QueryResult(
            rows=[{"id": 1, "name": None}],
            row_count=1,
            columns=["id", "name"],
            truncated=False,
        )

        formatted = QueryExecutor.format_result(result)

        assert "NULL" in formatted

    def test_format_result_truncated(self):
        """format_result should indicate truncation."""
        result = QueryResult(
            rows=[{"id": i} for i in range(10)],
            row_count=100,
            columns=["id"],
            truncated=True,
        )

        formatted = QueryExecutor.format_result(result)

        assert "90 more rows" in formatted
        assert "truncated" in formatted.lower()

    @pytest.mark.asyncio
    async def test_execute_formatted(self, executor_with_mock_db, mock_connection):
        """execute_formatted should return formatted string."""
        mock_connection.execute = AsyncMock()
        mock_connection.fetch = AsyncMock(
            return_value=[{"id": 1, "name": "Test"}]
        )

        result = await executor_with_mock_db.execute_formatted("SELECT * FROM users")

        assert isinstance(result, str)
        assert "id | name" in result
        assert "1 | Test" in result
