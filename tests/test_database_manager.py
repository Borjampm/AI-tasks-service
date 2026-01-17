"""Unit tests for DatabaseManager."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from database.manager import DatabaseManager


@pytest.fixture(autouse=True)
async def reset_singleton():
    """Reset DatabaseManager singleton before and after each test."""
    # Reset before test
    DatabaseManager._instance = None
    yield
    # Reset after test
    if DatabaseManager._instance is not None:
        try:
            await DatabaseManager._instance.close()
        except Exception:
            pass
        DatabaseManager._instance = None


class TestDatabaseManagerSingleton:
    """Tests for singleton pattern."""

    @pytest.mark.asyncio
    async def test_get_instance_creates_singleton(self):
        """get_instance should create and return the same instance."""
        with patch("database.manager.asyncpg.create_pool", new_callable=AsyncMock) as mock_pool:
            mock_pool.return_value = MagicMock()

            instance1 = await DatabaseManager.get_instance(
                database_url="postgresql://test"
            )
            instance2 = await DatabaseManager.get_instance()

            assert instance1 is instance2
            # Pool should only be created once
            assert mock_pool.call_count == 1

    @pytest.mark.asyncio
    async def test_reset_instance_clears_singleton(self):
        """reset_instance should clear the singleton."""
        with patch("database.manager.asyncpg.create_pool", new_callable=AsyncMock) as mock_pool:
            mock_pool.return_value = MagicMock()
            mock_pool.return_value.close = AsyncMock()

            instance1 = await DatabaseManager.get_instance(
                database_url="postgresql://test"
            )
            await DatabaseManager.reset_instance()
            instance2 = await DatabaseManager.get_instance(
                database_url="postgresql://test"
            )

            assert instance1 is not instance2
            assert mock_pool.call_count == 2


class TestDatabaseManagerInitialization:
    """Tests for initialization."""

    @pytest.mark.asyncio
    async def test_initialize_creates_pool(self):
        """initialize should create asyncpg pool."""
        with patch("database.manager.asyncpg.create_pool", new_callable=AsyncMock) as mock_pool:
            mock_pool.return_value = MagicMock()

            manager = DatabaseManager(database_url="postgresql://test")
            await manager.initialize()

            mock_pool.assert_called_once()
            call_kwargs = mock_pool.call_args.kwargs
            assert call_kwargs["statement_cache_size"] == 0  # Supabase requirement

    @pytest.mark.asyncio
    async def test_initialize_without_url_raises(self):
        """initialize should raise if no DATABASE_URL."""
        with patch.dict("os.environ", {}, clear=True):
            manager = DatabaseManager(database_url=None)

            with pytest.raises(ValueError) as exc_info:
                await manager.initialize()

            assert "DATABASE_URL" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_initialize_twice_warns(self):
        """initialize called twice should warn and not recreate pool."""
        with patch("database.manager.asyncpg.create_pool", new_callable=AsyncMock) as mock_pool:
            mock_pool.return_value = MagicMock()

            manager = DatabaseManager(database_url="postgresql://test")
            await manager.initialize()
            await manager.initialize()  # Second call

            # Should only create pool once
            assert mock_pool.call_count == 1

    @pytest.mark.asyncio
    async def test_pool_settings(self):
        """Pool should be created with correct settings."""
        with patch("database.manager.asyncpg.create_pool", new_callable=AsyncMock) as mock_pool:
            mock_pool.return_value = MagicMock()

            manager = DatabaseManager(
                database_url="postgresql://test",
                min_size=2,
                max_size=20,
            )
            await manager.initialize()

            call_kwargs = mock_pool.call_args.kwargs
            assert call_kwargs["min_size"] == 2
            assert call_kwargs["max_size"] == 20
            assert call_kwargs["statement_cache_size"] == 0


class TestDatabaseManagerConnection:
    """Tests for connection management."""

    @pytest.mark.asyncio
    async def test_connection_context_manager(self):
        """connection() should provide async context manager."""
        with patch("database.manager.asyncpg.create_pool", new_callable=AsyncMock) as mock_pool:
            mock_conn = AsyncMock()
            mock_pool_instance = MagicMock()
            mock_pool_instance.acquire = MagicMock(return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn),
                __aexit__=AsyncMock(return_value=None),
            ))
            mock_pool.return_value = mock_pool_instance

            manager = DatabaseManager(database_url="postgresql://test")
            await manager.initialize()

            async with manager.connection() as conn:
                assert conn is mock_conn

    @pytest.mark.asyncio
    async def test_connection_without_init_raises(self):
        """connection() should raise if pool not initialized."""
        manager = DatabaseManager(database_url="postgresql://test")

        with pytest.raises(RuntimeError) as exc_info:
            async with manager.connection():
                pass

        assert "not initialized" in str(exc_info.value)


class TestDatabaseManagerClose:
    """Tests for closing connections."""

    @pytest.mark.asyncio
    async def test_close_closes_pool(self):
        """close should close the pool."""
        with patch("database.manager.asyncpg.create_pool", new_callable=AsyncMock) as mock_pool:
            mock_pool_instance = MagicMock()
            mock_pool_instance.close = AsyncMock()
            mock_pool.return_value = mock_pool_instance

            manager = DatabaseManager(database_url="postgresql://test")
            await manager.initialize()
            await manager.close()

            mock_pool_instance.close.assert_called_once()
            assert manager.pool is None

    @pytest.mark.asyncio
    async def test_close_when_not_initialized(self):
        """close should be safe when pool not initialized."""
        manager = DatabaseManager(database_url="postgresql://test")
        await manager.close()  # Should not raise


class TestDatabaseManagerPoolStatus:
    """Tests for pool status reporting."""

    @pytest.mark.asyncio
    async def test_pool_status_initialized(self):
        """pool_status should return metrics when initialized."""
        with patch("database.manager.asyncpg.create_pool", new_callable=AsyncMock) as mock_pool:
            mock_pool_instance = MagicMock()
            mock_pool_instance.get_size.return_value = 5
            mock_pool_instance.get_idle_size.return_value = 3
            mock_pool.return_value = mock_pool_instance

            manager = DatabaseManager(
                database_url="postgresql://test",
                min_size=1,
                max_size=10,
            )
            await manager.initialize()

            status = manager.pool_status

            assert status["status"] == "initialized"
            assert status["size"] == 5
            assert status["idle_size"] == 3
            assert status["min_size"] == 1
            assert status["max_size"] == 10

    def test_pool_status_not_initialized(self):
        """pool_status should indicate not initialized."""
        manager = DatabaseManager(database_url="postgresql://test")

        status = manager.pool_status

        assert status["status"] == "not_initialized"


class TestDatabaseManagerIsInitialized:
    """Tests for is_initialized property."""

    def test_is_initialized_false_by_default(self):
        """is_initialized should be False before initialization."""
        manager = DatabaseManager(database_url="postgresql://test")
        assert manager.is_initialized is False

    @pytest.mark.asyncio
    async def test_is_initialized_true_after_init(self):
        """is_initialized should be True after initialization."""
        with patch("database.manager.asyncpg.create_pool", new_callable=AsyncMock) as mock_pool:
            mock_pool.return_value = MagicMock()

            manager = DatabaseManager(database_url="postgresql://test")
            await manager.initialize()

            assert manager.is_initialized is True

    @pytest.mark.asyncio
    async def test_is_initialized_false_after_close(self):
        """is_initialized should be False after close."""
        with patch("database.manager.asyncpg.create_pool", new_callable=AsyncMock) as mock_pool:
            mock_pool_instance = MagicMock()
            mock_pool_instance.close = AsyncMock()
            mock_pool.return_value = mock_pool_instance

            manager = DatabaseManager(database_url="postgresql://test")
            await manager.initialize()
            await manager.close()

            assert manager.is_initialized is False
