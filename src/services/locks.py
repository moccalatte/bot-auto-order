"""Distributed lock helpers backed by PostgreSQL advisory locks."""

from __future__ import annotations

import hashlib
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from src.services.postgres import get_pool


logger = logging.getLogger(__name__)


class LockNotAcquired(RuntimeError):
    """Raised when a distributed lock cannot be obtained."""


def _lock_key(name: str) -> int:
    """Return a stable 64-bit integer for the given lock name."""
    digest = hashlib.sha256(name.encode("utf-8")).digest()
    # Use the first 8 bytes as a signed 64-bit integer.
    return int.from_bytes(digest[:8], byteorder="big", signed=True)


@asynccontextmanager
async def distributed_lock(name: str) -> AsyncIterator[None]:
    """Acquire an advisory lock identified by ``name``.

    Releases the lock automatically when the context exits.
    """

    pool = await get_pool()
    lock_id = _lock_key(name)
    async with pool.acquire() as connection:
        acquired = await connection.fetchval(
            "SELECT pg_try_advisory_lock($1);", lock_id
        )
        if not acquired:
            logger.debug("[lock] %s already held by another worker.", name)
            raise LockNotAcquired(f"Lock '{name}' is already held.")

        try:
            yield
        finally:
            await connection.fetchval("SELECT pg_advisory_unlock($1);", lock_id)
            logger.debug("[lock] %s released.", name)
