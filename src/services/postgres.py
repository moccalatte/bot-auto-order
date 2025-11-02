"""PostgreSQL access layer using asyncpg."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Iterable

import asyncpg

from src.core.config import get_settings


logger = logging.getLogger(__name__)


class PostgresPool:
    """Wrapper around asyncpg connection pool."""

    def __init__(self, dsn: str, min_size: int = 1, max_size: int = 10) -> None:
        if dsn.startswith("postgresql+asyncpg://"):
            dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
        self._dsn = dsn
        self._min_size = min_size
        self._max_size = max_size
        self._pool: asyncpg.Pool | None = None
        self._lock = asyncio.Lock()

    async def init(self) -> None:
        """Initialise connection pool."""
        async with self._lock:
            if self._pool is None:
                self._pool = await asyncpg.create_pool(
                    dsn=self._dsn,
                    min_size=self._min_size,
                    max_size=self._max_size,
                )
                logger.info("🔌 Connected to Postgres.")

    async def close(self) -> None:
        """Close pool and release resources."""
        async with self._lock:
            if self._pool is not None:
                await self._pool.close()
                self._pool = None
                logger.info("🔌 Postgres pool closed.")

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[asyncpg.Connection]:
        """Acquire a raw asyncpg connection."""
        if self._pool is None:
            raise RuntimeError("Postgres pool not initialised.")
        async with self._pool.acquire() as connection:
            yield connection

    async def fetch(self, query: str, *args: Any) -> Iterable[asyncpg.Record]:
        """Run SELECT returning multiple rows."""
        async with self.acquire() as connection:
            return await connection.fetch(query, *args)

    async def fetchrow(self, query: str, *args: Any) -> asyncpg.Record | None:
        """Run SELECT returning single row."""
        async with self.acquire() as connection:
            return await connection.fetchrow(query, *args)

    async def execute(self, query: str, *args: Any) -> str:
        """Execute statement without returning rows."""
        async with self.acquire() as connection:
            return await connection.execute(query, *args)


_pg_pool: PostgresPool | None = None


async def get_pool() -> PostgresPool:
    """Return shared Postgres pool instance."""
    global _pg_pool  # noqa: PLW0603
    if _pg_pool is None:
        settings = get_settings()
        _pg_pool = PostgresPool(settings.database_url)
        await _pg_pool.init()
    return _pg_pool
