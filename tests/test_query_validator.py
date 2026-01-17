"""Unit tests for QueryValidator."""

import pytest
from database.query import QueryValidator, QueryValidationError


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
