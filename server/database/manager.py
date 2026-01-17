"""Database connection manager with singleton pattern for Supabase."""

import asyncio
import asyncpg
import os
import logging
from typing import Optional, AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")


class DatabaseManager:
    """Singleton database connection manager for Supabase.

    Handles connection pooling with Supabase pooler compatibility
    (statement_cache_size=0 required for pgbouncer).

    Usage:
        db = await DatabaseManager.get_instance()
        async with db.connection() as conn:
            rows = await conn.fetch("SELECT * FROM users")

        # When shutting down:
        await db.close()
    """

    _instance: Optional["DatabaseManager"] = None
    _lock = asyncio.Lock()

    def __init__(
        self,
        database_url: Optional[str] = None,
        min_size: int = 1,
        max_size: int = 10,
    ):
        """Initialize DatabaseManager (use get_instance() instead).

        Args:
            database_url: PostgreSQL connection string. Defaults to DATABASE_URL env var.
            min_size: Minimum connections in pool.
            max_size: Maximum connections in pool.
        """
        self.database_url = database_url or os.getenv("DATABASE_URL")
        self.min_size = min_size
        self.max_size = max_size
        self.pool: Optional[asyncpg.Pool] = None
        self.logger = logging.getLogger(__name__)

    @classmethod
    async def get_instance(
        cls,
        database_url: Optional[str] = None,
        min_size: int = 1,
        max_size: int = 10,
    ) -> "DatabaseManager":
        """Get or create the singleton instance.

        Args:
            database_url: PostgreSQL connection string (only used on first call).
            min_size: Minimum connections in pool (only used on first call).
            max_size: Maximum connections in pool (only used on first call).

        Returns:
            The singleton DatabaseManager instance.
        """
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = DatabaseManager(
                        database_url=database_url,
                        min_size=min_size,
                        max_size=max_size,
                    )
                    await cls._instance.initialize()
        return cls._instance

    @classmethod
    async def reset_instance(cls) -> None:
        """Reset the singleton (for testing). Closes existing pool."""
        if cls._instance is not None:
            await cls._instance.close()
            cls._instance = None

    async def initialize(self) -> None:
        """Initialize the connection pool."""
        if not self.database_url:
            raise ValueError("DATABASE_URL not configured")

        if self.pool is not None:
            self.logger.warning("Pool already initialized")
            return

        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=self.min_size,
                max_size=self.max_size,
                statement_cache_size=0,  # Required for Supabase pooler
            )
            self.logger.info(
                f"Database pool initialized (min={self.min_size}, max={self.max_size})"
            )
        except Exception as e:
            self.logger.error(f"Failed to initialize database pool: {e}")
            raise

    async def close(self) -> None:
        """Close all connections in the pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            self.logger.info("Database pool closed")

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[asyncpg.Connection]:
        """Context manager for acquiring a connection from the pool.

        Usage:
            async with db.connection() as conn:
                rows = await conn.fetch("SELECT * FROM users")

        Yields:
            asyncpg.Connection: A connection from the pool.

        Raises:
            RuntimeError: If pool is not initialized.
        """
        if not self.pool:
            raise RuntimeError("Database pool not initialized. Call initialize() first.")

        async with self.pool.acquire() as conn:
            yield conn

    @property
    def pool_status(self) -> dict:
        """Get current pool status metrics.

        Returns:
            dict with pool statistics:
                - status: "initialized" or "not_initialized"
                - size: Total connections in pool
                - idle_size: Available connections
                - min_size: Configured minimum
                - max_size: Configured maximum
        """
        if not self.pool:
            return {"status": "not_initialized"}

        return {
            "status": "initialized",
            "size": self.pool.get_size(),
            "idle_size": self.pool.get_idle_size(),
            "min_size": self.min_size,
            "max_size": self.max_size,
        }

    @property
    def is_initialized(self) -> bool:
        """Check if the pool is initialized."""
        return self.pool is not None
