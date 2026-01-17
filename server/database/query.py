"""Query validation and execution for read-only database access."""

import asyncio
import re
import logging
from typing import Optional, List, Any
from dataclasses import dataclass

import asyncpg

from .manager import DatabaseManager


class QueryValidationError(Exception):
    """Raised when a query fails validation."""

    pass


class QueryExecutionError(Exception):
    """Raised when a query fails to execute.

    Attributes:
        original_error: The underlying exception that caused this error.
    """

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.original_error = original_error
        if original_error:
            self.__cause__ = original_error


@dataclass
class QueryResult:
    """Structured result from query execution."""

    rows: List[dict]
    row_count: int
    columns: List[str]
    truncated: bool = False


class QueryValidator:
    """Validates SQL queries for safety (read-only enforcement)."""

    FORBIDDEN_KEYWORDS = frozenset(
        {
            "INSERT",
            "UPDATE",
            "DELETE",
            "DROP",
            "ALTER",
            "CREATE",
            "TRUNCATE",
            "GRANT",
            "REVOKE",
            "VACUUM",
            "ANALYZE",
        }
    )

    ALLOWED_PREFIXES = frozenset({"SELECT", "WITH", "EXPLAIN"})

    @classmethod
    def validate(cls, sql: str, user_id: Optional[str] = None) -> None:
        """Validate SQL query for safety.

        Args:
            sql: The SQL query to validate.
            user_id: If provided, query must include user_id filter.

        Raises:
            QueryValidationError: If query is unsafe.
        """
        sql_clean = sql.strip()
        sql_upper = sql_clean.upper()

        # Must start with allowed keyword
        if not any(sql_upper.startswith(prefix) for prefix in cls.ALLOWED_PREFIXES):
            raise QueryValidationError(
                "Only SELECT queries are allowed. "
                f"Query must start with: {', '.join(cls.ALLOWED_PREFIXES)}"
            )

        # Check for forbidden keywords (as whole words)
        for keyword in cls.FORBIDDEN_KEYWORDS:
            if re.search(rf"\b{keyword}\b", sql_upper):
                raise QueryValidationError(
                    f"Query contains forbidden keyword '{keyword}'. "
                    "Only read-only queries are allowed."
                )

        # Enforce user_id filtering for multi-tenant isolation
        if user_id and "user_id" not in sql.lower():
            raise QueryValidationError(
                f"Query must include user_id filter for data isolation. "
                f"Add: WHERE user_id = '{user_id}'"
            )


class QueryExecutor:
    """Executes validated queries with result formatting."""

    # Base delay for exponential backoff retries (in seconds)
    RETRY_BASE_DELAY_SECONDS = 0.1

    def __init__(
        self,
        db_manager: DatabaseManager,
        max_rows: int = 100,
        max_retries: int = 3,
    ):
        """Initialize QueryExecutor.

        Args:
            db_manager: DatabaseManager instance for connections.
            max_rows: Maximum rows to return (prevents large result sets).
            max_retries: Number of retries on transient failures.
        """
        self.db = db_manager
        self.max_rows = max_rows
        self.max_retries = max_retries
        self.logger = logging.getLogger(__name__)

    async def execute(
        self,
        sql: str,
        user_id: Optional[str] = None,
        validate: bool = True,
    ) -> QueryResult:
        """Execute a read-only query with validation.

        Args:
            sql: SELECT query to execute.
            user_id: If provided, validates query includes user_id filter.
            validate: Whether to validate the query first.

        Returns:
            QueryResult with rows, columns, and metadata.

        Raises:
            QueryValidationError: If query fails validation.
            QueryExecutionError: If query fails to execute.
        """
        sql = sql.strip()

        if validate:
            QueryValidator.validate(sql, user_id)

        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                async with self.db.connection() as conn:
                    # Validate with EXPLAIN first (catches syntax errors)
                    await conn.execute(f"EXPLAIN {sql}")

                    # Execute the actual query
                    rows = await conn.fetch(sql)

                    # Convert to list of dicts
                    rows_list = [dict(row) for row in rows]
                    truncated = len(rows_list) > self.max_rows

                    if truncated:
                        rows_list = rows_list[: self.max_rows]

                    columns = list(rows[0].keys()) if rows else []

                    return QueryResult(
                        rows=rows_list,
                        row_count=len(rows),
                        columns=columns,
                        truncated=truncated,
                    )

            except asyncpg.PostgresError as e:
                last_error = e
                self.logger.warning(
                    f"Query attempt {attempt + 1}/{self.max_retries} failed: {e}"
                )

                # Don't retry on syntax/semantic errors
                if "syntax error" in str(e).lower():
                    raise QueryExecutionError(f"SQL syntax error: {e}", original_error=e)

                if attempt < self.max_retries - 1:
                    delay = self.RETRY_BASE_DELAY_SECONDS * (2**attempt)
                    await asyncio.sleep(delay)

            except QueryExecutionError:
                raise  # Re-raise our own exceptions without wrapping

            except Exception as e:
                raise QueryExecutionError(f"Query execution failed: {e}", original_error=e)

        raise QueryExecutionError(
            f"Query failed after {self.max_retries} attempts: {last_error}",
            original_error=last_error,
        )

    async def execute_formatted(
        self,
        sql: str,
        user_id: Optional[str] = None,
    ) -> str:
        """Execute query and return formatted string for AI consumption.

        Args:
            sql: SELECT query to execute.
            user_id: If provided, validates query includes user_id filter.

        Returns:
            Formatted string with results in table format.
        """
        result = await self.execute(sql, user_id)
        return self.format_result(result)

    @staticmethod
    def format_result(result: QueryResult) -> str:
        """Format QueryResult as a human-readable string.

        Args:
            result: QueryResult to format.

        Returns:
            Formatted string with columns and rows.
        """
        if not result.rows:
            return "No results found."

        lines = []

        # Header
        lines.append(" | ".join(result.columns))
        lines.append("-" * len(lines[0]))

        # Rows
        for row in result.rows:
            values = [str(v) if v is not None else "NULL" for v in row.values()]
            lines.append(" | ".join(values))

        # Truncation notice
        if result.truncated:
            remaining = result.row_count - len(result.rows)
            lines.append(f"... and {remaining} more rows (truncated)")

        return "\n".join(lines)
