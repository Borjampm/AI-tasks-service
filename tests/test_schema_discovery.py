"""Unit tests for SchemaDiscovery."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from contextlib import asynccontextmanager

from database.schema import SchemaDiscovery, TableInfo, ColumnInfo
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
def schema_with_mock_db(mock_db_manager, mock_connection):
    """Create SchemaDiscovery with mocked database."""

    @asynccontextmanager
    async def mock_connection_cm():
        yield mock_connection

    mock_db_manager.connection = mock_connection_cm
    return SchemaDiscovery(mock_db_manager)


@pytest.fixture
def sample_schema_rows():
    """Sample schema data from information_schema.columns."""
    return [
        {
            "table_name": "users",
            "column_name": "id",
            "data_type": "uuid",
            "is_nullable": "NO",
            "column_default": "gen_random_uuid()",
            "column_comment": "Primary key",
        },
        {
            "table_name": "users",
            "column_name": "name",
            "data_type": "text",
            "is_nullable": "YES",
            "column_default": None,
            "column_comment": None,
        },
        {
            "table_name": "transactions",
            "column_name": "id",
            "data_type": "uuid",
            "is_nullable": "NO",
            "column_default": None,
            "column_comment": None,
        },
        {
            "table_name": "transactions",
            "column_name": "amount",
            "data_type": "numeric",
            "is_nullable": "NO",
            "column_default": None,
            "column_comment": "Transaction amount",
        },
        {
            "table_name": "transactions",
            "column_name": "user_id",
            "data_type": "uuid",
            "is_nullable": "NO",
            "column_default": None,
            "column_comment": "Foreign key to users",
        },
    ]


class TestSchemaDiscoveryRefresh:
    """Tests for schema refresh."""

    @pytest.mark.asyncio
    async def test_refresh_loads_schema(
        self, schema_with_mock_db, mock_connection, sample_schema_rows
    ):
        """refresh should load schema from database."""
        mock_connection.fetch = AsyncMock(return_value=sample_schema_rows)

        await schema_with_mock_db.refresh()

        assert schema_with_mock_db.is_loaded is True
        mock_connection.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_parses_tables(
        self, schema_with_mock_db, mock_connection, sample_schema_rows
    ):
        """refresh should parse tables correctly."""
        mock_connection.fetch = AsyncMock(return_value=sample_schema_rows)

        await schema_with_mock_db.refresh()

        tables = schema_with_mock_db.get_tables()
        assert "users" in tables
        assert "transactions" in tables
        assert len(tables) == 2

    @pytest.mark.asyncio
    async def test_refresh_parses_columns(
        self, schema_with_mock_db, mock_connection, sample_schema_rows
    ):
        """refresh should parse columns correctly."""
        mock_connection.fetch = AsyncMock(return_value=sample_schema_rows)

        await schema_with_mock_db.refresh()

        users_table = schema_with_mock_db.get_table("users")
        assert users_table is not None
        assert len(users_table.columns) == 2
        assert users_table.columns[0].name == "id"
        assert users_table.columns[0].data_type == "uuid"
        assert users_table.columns[0].is_nullable is False
        assert users_table.columns[1].name == "name"
        assert users_table.columns[1].is_nullable is True

    @pytest.mark.asyncio
    async def test_refresh_clears_previous_cache(
        self, schema_with_mock_db, mock_connection
    ):
        """refresh should clear previous cache."""
        # First load
        mock_connection.fetch = AsyncMock(
            return_value=[
                {
                    "table_name": "old_table",
                    "column_name": "id",
                    "data_type": "int",
                    "is_nullable": "NO",
                    "column_default": None,
                    "column_comment": None,
                }
            ]
        )
        await schema_with_mock_db.refresh()
        assert "old_table" in schema_with_mock_db.get_tables()

        # Second load with different data
        mock_connection.fetch = AsyncMock(
            return_value=[
                {
                    "table_name": "new_table",
                    "column_name": "id",
                    "data_type": "int",
                    "is_nullable": "NO",
                    "column_default": None,
                    "column_comment": None,
                }
            ]
        )
        await schema_with_mock_db.refresh()

        tables = schema_with_mock_db.get_tables()
        assert "new_table" in tables
        assert "old_table" not in tables


class TestSchemaDiscoveryGetters:
    """Tests for getter methods."""

    @pytest.mark.asyncio
    async def test_get_tables_returns_sorted_list(
        self, schema_with_mock_db, mock_connection, sample_schema_rows
    ):
        """get_tables should return sorted list of table names."""
        mock_connection.fetch = AsyncMock(return_value=sample_schema_rows)
        await schema_with_mock_db.refresh()

        tables = schema_with_mock_db.get_tables()

        assert tables == ["transactions", "users"]  # Sorted alphabetically

    def test_get_tables_raises_if_not_loaded(self, schema_with_mock_db):
        """get_tables should raise if schema not loaded."""
        with pytest.raises(RuntimeError) as exc_info:
            schema_with_mock_db.get_tables()

        assert "not loaded" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_get_table_returns_table_info(
        self, schema_with_mock_db, mock_connection, sample_schema_rows
    ):
        """get_table should return TableInfo for existing table."""
        mock_connection.fetch = AsyncMock(return_value=sample_schema_rows)
        await schema_with_mock_db.refresh()

        table = schema_with_mock_db.get_table("users")

        assert isinstance(table, TableInfo)
        assert table.name == "users"
        assert len(table.columns) == 2

    @pytest.mark.asyncio
    async def test_get_table_returns_none_for_missing(
        self, schema_with_mock_db, mock_connection, sample_schema_rows
    ):
        """get_table should return None for non-existent table."""
        mock_connection.fetch = AsyncMock(return_value=sample_schema_rows)
        await schema_with_mock_db.refresh()

        table = schema_with_mock_db.get_table("nonexistent")

        assert table is None

    def test_get_table_raises_if_not_loaded(self, schema_with_mock_db):
        """get_table should raise if schema not loaded."""
        with pytest.raises(RuntimeError):
            schema_with_mock_db.get_table("users")

    @pytest.mark.asyncio
    async def test_get_all_tables(
        self, schema_with_mock_db, mock_connection, sample_schema_rows
    ):
        """get_all_tables should return dict of all tables."""
        mock_connection.fetch = AsyncMock(return_value=sample_schema_rows)
        await schema_with_mock_db.refresh()

        all_tables = schema_with_mock_db.get_all_tables()

        assert isinstance(all_tables, dict)
        assert "users" in all_tables
        assert "transactions" in all_tables
        assert isinstance(all_tables["users"], TableInfo)


class TestSchemaDiscoveryContextBuilding:
    """Tests for context building methods."""

    @pytest.mark.asyncio
    async def test_build_context_for_agent(
        self, schema_with_mock_db, mock_connection, sample_schema_rows
    ):
        """build_context_for_agent should create formatted string."""
        mock_connection.fetch = AsyncMock(return_value=sample_schema_rows)
        await schema_with_mock_db.refresh()

        context = schema_with_mock_db.build_context_for_agent()

        assert "## Database Schema" in context
        assert "### users" in context
        assert "### transactions" in context
        assert "`id`: uuid (NOT NULL)" in context
        assert "`name`: text (NULL)" in context
        assert "`amount`: numeric (NOT NULL)" in context

    @pytest.mark.asyncio
    async def test_build_context_includes_comments(
        self, schema_with_mock_db, mock_connection, sample_schema_rows
    ):
        """build_context_for_agent should include column comments."""
        mock_connection.fetch = AsyncMock(return_value=sample_schema_rows)
        await schema_with_mock_db.refresh()

        context = schema_with_mock_db.build_context_for_agent()

        assert "Primary key" in context
        assert "Transaction amount" in context

    def test_build_context_raises_if_not_loaded(self, schema_with_mock_db):
        """build_context_for_agent should raise if not loaded."""
        with pytest.raises(RuntimeError):
            schema_with_mock_db.build_context_for_agent()

    @pytest.mark.asyncio
    async def test_build_table_context(
        self, schema_with_mock_db, mock_connection, sample_schema_rows
    ):
        """build_table_context should create context for single table."""
        mock_connection.fetch = AsyncMock(return_value=sample_schema_rows)
        await schema_with_mock_db.refresh()

        context = schema_with_mock_db.build_table_context("transactions")

        assert "### transactions" in context
        assert "`amount`: numeric (NOT NULL)" in context
        assert "### users" not in context  # Should not include other table headers

    @pytest.mark.asyncio
    async def test_build_table_context_returns_none_for_missing(
        self, schema_with_mock_db, mock_connection, sample_schema_rows
    ):
        """build_table_context should return None for missing table."""
        mock_connection.fetch = AsyncMock(return_value=sample_schema_rows)
        await schema_with_mock_db.refresh()

        context = schema_with_mock_db.build_table_context("nonexistent")

        assert context is None


class TestTableInfo:
    """Tests for TableInfo dataclass."""

    def test_column_names_property(self):
        """column_names should return list of column names."""
        table = TableInfo(
            name="test",
            columns=[
                ColumnInfo(name="id", data_type="int", is_nullable=False),
                ColumnInfo(name="name", data_type="text", is_nullable=True),
            ],
        )

        assert table.column_names == ["id", "name"]

    def test_empty_columns(self):
        """Table with no columns should return empty list."""
        table = TableInfo(name="empty", columns=[])

        assert table.column_names == []


class TestColumnInfo:
    """Tests for ColumnInfo dataclass."""

    def test_default_values(self):
        """ColumnInfo should have correct defaults."""
        col = ColumnInfo(name="test", data_type="text", is_nullable=True)

        assert col.default is None
        assert col.comment is None

    def test_all_fields(self):
        """ColumnInfo should store all fields."""
        col = ColumnInfo(
            name="id",
            data_type="uuid",
            is_nullable=False,
            default="gen_random_uuid()",
            comment="Primary key",
        )

        assert col.name == "id"
        assert col.data_type == "uuid"
        assert col.is_nullable is False
        assert col.default == "gen_random_uuid()"
        assert col.comment == "Primary key"
