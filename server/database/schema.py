"""Schema discovery for database introspection."""

import logging
from typing import Optional, Dict, List
from dataclasses import dataclass, field

from .manager import DatabaseManager


@dataclass
class ColumnInfo:
    """Information about a database column."""

    name: str
    data_type: str
    is_nullable: bool
    default: Optional[str] = None
    comment: Optional[str] = None


@dataclass
class TableInfo:
    """Information about a database table."""

    name: str
    columns: List[ColumnInfo] = field(default_factory=list)
    comment: Optional[str] = None

    @property
    def column_names(self) -> List[str]:
        """Get list of column names."""
        return [col.name for col in self.columns]


class SchemaDiscovery:
    """Discovers and caches database schema information.

    Usage:
        schema = SchemaDiscovery(db_manager)
        await schema.refresh()  # Load schema from database

        tables = schema.get_tables()
        table_info = schema.get_table("transactions")
        context = schema.build_context_for_agent()
    """

    def __init__(self, db_manager: DatabaseManager):
        """Initialize SchemaDiscovery.

        Args:
            db_manager: DatabaseManager instance for connections.
        """
        self.db = db_manager
        self.logger = logging.getLogger(__name__)
        self._cache: Dict[str, TableInfo] = {}
        self._is_loaded: bool = False

    @property
    def is_loaded(self) -> bool:
        """Check if schema has been loaded."""
        return self._is_loaded

    async def refresh(self) -> None:
        """Refresh schema cache from database."""
        self.logger.info("Refreshing schema cache...")

        async with self.db.connection() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    c.table_name,
                    c.column_name,
                    c.data_type,
                    c.is_nullable,
                    c.column_default,
                    pgd.description as column_comment
                FROM information_schema.columns c
                LEFT JOIN pg_catalog.pg_statio_all_tables st
                    ON c.table_schema = st.schemaname
                    AND c.table_name = st.relname
                LEFT JOIN pg_catalog.pg_description pgd
                    ON pgd.objoid = st.relid
                    AND pgd.objsubid = c.ordinal_position
                WHERE c.table_schema = 'public'
                ORDER BY c.table_name, c.ordinal_position
                """
            )

        # Parse into schema cache
        self._cache = {}
        for row in rows:
            table_name = row["table_name"]

            if table_name not in self._cache:
                self._cache[table_name] = TableInfo(name=table_name)

            self._cache[table_name].columns.append(
                ColumnInfo(
                    name=row["column_name"],
                    data_type=row["data_type"],
                    is_nullable=row["is_nullable"] == "YES",
                    default=row["column_default"],
                    comment=row["column_comment"],
                )
            )

        self._is_loaded = True
        self.logger.info(f"Schema cache loaded: {len(self._cache)} tables")

    def get_tables(self) -> List[str]:
        """Get list of table names.

        Returns:
            Sorted list of table names.

        Raises:
            RuntimeError: If schema not loaded.
        """
        self._ensure_loaded()
        return sorted(self._cache.keys())

    def get_table(self, table_name: str) -> Optional[TableInfo]:
        """Get schema for a specific table.

        Args:
            table_name: Name of the table.

        Returns:
            TableInfo if found, None otherwise.

        Raises:
            RuntimeError: If schema not loaded.
        """
        self._ensure_loaded()
        return self._cache.get(table_name)

    def get_all_tables(self) -> Dict[str, TableInfo]:
        """Get all table schemas.

        Returns:
            Dictionary of table_name -> TableInfo.

        Raises:
            RuntimeError: If schema not loaded.
        """
        self._ensure_loaded()
        return self._cache.copy()

    def build_context_for_agent(self) -> str:
        """Build schema context string for AI agent system prompt.

        Returns:
            Formatted string describing all tables and columns.

        Raises:
            RuntimeError: If schema not loaded.
        """
        self._ensure_loaded()

        lines = [
            "## Database Schema",
            "",
            "The database contains the following tables:",
            "",
        ]

        for table_name in sorted(self._cache.keys()):
            table = self._cache[table_name]
            lines.append(f"### {table_name}")

            if table.comment:
                lines.append(f"_{table.comment}_")
                lines.append("")

            lines.append("Columns:")
            for col in table.columns:
                nullable = "NULL" if col.is_nullable else "NOT NULL"
                col_line = f"  - `{col.name}`: {col.data_type} ({nullable})"
                if col.comment:
                    col_line += f" -- {col.comment}"
                lines.append(col_line)

            lines.append("")

        return "\n".join(lines)

    def build_table_context(self, table_name: str) -> Optional[str]:
        """Build context string for a single table.

        Args:
            table_name: Name of the table.

        Returns:
            Formatted string for the table, or None if not found.
        """
        table = self.get_table(table_name)
        if not table:
            return None

        lines = [f"### {table_name}", ""]

        if table.comment:
            lines.append(f"_{table.comment}_")
            lines.append("")

        lines.append("Columns:")
        for col in table.columns:
            nullable = "NULL" if col.is_nullable else "NOT NULL"
            col_line = f"  - `{col.name}`: {col.data_type} ({nullable})"
            if col.comment:
                col_line += f" -- {col.comment}"
            lines.append(col_line)

        return "\n".join(lines)

    def _ensure_loaded(self) -> None:
        """Ensure schema is loaded, raise if not."""
        if not self._is_loaded:
            raise RuntimeError(
                "Schema not loaded. Call refresh() first to load schema from database."
            )
