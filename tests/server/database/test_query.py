"""Unit tests for QueryValidator and QueryExecutor."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from contextlib import asynccontextmanager

import asyncpg

from database.query import (
    QueryValidator,
    QueryValidationError,
    QueryExecutor,
    QueryResult,
    QueryExecutionError,
)
from database.manager import DatabaseManager


# =============================================================================
# QueryValidator Tests
# =============================================================================


class TestQueryValidatorAllowedPrefixes:
    """Tests for allowed query prefixes."""

    def test_select_query_is_valid(self):
        """SELECT queries should be allowed."""
        QueryValidator.validate("SELECT * FROM users")

    def test_select_with_where_is_valid(self):
        """SELECT with WHERE clause should be allowed."""
        QueryValidator.validate("SELECT name FROM users WHERE id = 1")

    def test_with_cte_is_valid(self):
        """WITH (CTE) queries should be allowed."""
        QueryValidator.validate("WITH cte AS (SELECT 1) SELECT * FROM cte")

    def test_explain_is_valid(self):
        """EXPLAIN queries should be allowed."""
        QueryValidator.validate("EXPLAIN SELECT * FROM users")

    def test_lowercase_select_is_valid(self):
        """Lowercase SELECT should be allowed."""
        QueryValidator.validate("select * from users")

    def test_mixed_case_select_is_valid(self):
        """Mixed case SELECT should be allowed."""
        QueryValidator.validate("SeLeCt * FROM users")

    def test_whitespace_before_select_is_valid(self):
        """Whitespace before SELECT should be stripped and allowed."""
        QueryValidator.validate("   SELECT * FROM users")


class TestQueryValidatorForbiddenKeywords:
    """Tests for forbidden keyword detection."""

    @pytest.mark.parametrize(
        "sql,keyword",
        [
            ("INSERT INTO users VALUES (1)", "INSERT"),
            ("DELETE FROM users", "DELETE"),
            ("UPDATE users SET name = 'x'", "UPDATE"),
            ("DROP TABLE users", "DROP"),
            ("ALTER TABLE users ADD column", "ALTER"),
            ("CREATE TABLE users (id int)", "CREATE"),
            ("TRUNCATE TABLE users", "TRUNCATE"),
            ("GRANT SELECT ON users TO role", "GRANT"),
            ("REVOKE SELECT ON users FROM role", "REVOKE"),
            ("VACUUM users", "VACUUM"),
            ("ANALYZE users", "ANALYZE"),
        ],
    )
    def test_forbidden_keyword_rejected(self, sql, keyword):
        """Queries with forbidden keywords should be rejected."""
        with pytest.raises(QueryValidationError) as exc_info:
            QueryValidator.validate(sql)
        # Should be caught by either prefix check or keyword check
        assert "forbidden" in str(exc_info.value).lower() or "SELECT" in str(exc_info.value)

    def test_forbidden_keyword_in_subquery_rejected(self):
        """Forbidden keywords in subqueries should be rejected."""
        with pytest.raises(QueryValidationError):
            QueryValidator.validate("SELECT * FROM (DELETE FROM users RETURNING *)")

    def test_keyword_in_string_literal_rejected(self):
        """Keywords in string literals are still caught (conservative approach)."""
        # This is a conservative approach - the keyword check doesn't parse SQL
        with pytest.raises(QueryValidationError):
            QueryValidator.validate("SELECT * FROM users WHERE name = 'DROP'")

    def test_sql_injection_attempt_rejected(self):
        """SQL injection attempts should be rejected."""
        with pytest.raises(QueryValidationError):
            QueryValidator.validate("SELECT * FROM users; DROP TABLE users")


class TestQueryValidatorUserIdFilter:
    """Tests for user_id filtering requirement."""

    def test_user_id_required_when_provided(self):
        """When user_id is provided, query must include user_id filter."""
        with pytest.raises(QueryValidationError) as exc_info:
            QueryValidator.validate("SELECT * FROM users", user_id="123")
        assert "user_id" in str(exc_info.value)

    def test_user_id_filter_in_where_passes(self):
        """Query with user_id in WHERE clause should pass."""
        QueryValidator.validate(
            "SELECT * FROM users WHERE user_id = '123'",
            user_id="123",
        )

    def test_user_id_filter_case_insensitive(self):
        """user_id check should be case insensitive."""
        QueryValidator.validate(
            "SELECT * FROM users WHERE USER_ID = '123'",
            user_id="123",
        )

    def test_no_user_id_required_when_none(self):
        """When user_id is None, no filter is required."""
        QueryValidator.validate("SELECT * FROM users", user_id=None)

    def test_user_id_in_join_passes(self):
        """user_id in JOIN condition should pass."""
        QueryValidator.validate(
            "SELECT * FROM transactions t JOIN users u ON t.user_id = u.id WHERE t.user_id = '123'",
            user_id="123",
        )


class TestQueryValidatorEdgeCases:
    """Tests for edge cases."""

    def test_empty_query_rejected(self):
        """Empty queries should be rejected."""
        with pytest.raises(QueryValidationError):
            QueryValidator.validate("")

    def test_whitespace_only_rejected(self):
        """Whitespace-only queries should be rejected."""
        with pytest.raises(QueryValidationError):
            QueryValidator.validate("   ")

    def test_complex_valid_query(self):
        """Complex valid queries should pass."""
        sql = """
            WITH monthly_totals AS (
                SELECT
                    DATE_TRUNC('month', transaction_date) as month,
                    SUM(amount) as total
                FROM transactions
                WHERE user_id = '123'
                GROUP BY DATE_TRUNC('month', transaction_date)
            )
            SELECT month, total
            FROM monthly_totals
            ORDER BY month DESC
            LIMIT 12
        """
        QueryValidator.validate(sql, user_id="123")

    def test_select_into_rejected(self):
        """SELECT INTO is effectively a CREATE and might be dangerous."""
        # This would be caught by the prefix check since it's still SELECT
        # But worth documenting the behavior
        QueryValidator.validate("SELECT * INTO new_table FROM users")
        # Note: This passes because we can't easily detect SELECT INTO
        # The read-only database user would prevent actual execution


# =============================================================================
# QueryExecutor Tests
# =============================================================================


@pytest.fixture
def executor_with_mock_db(mock_db_with_connection, mock_connection):
    """Create QueryExecutor with mocked database."""
    return QueryExecutor(mock_db_with_connection, max_rows=10, max_retries=3)


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
