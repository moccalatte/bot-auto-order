"""Helpers for managing customer deposits."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from src.services.postgres import get_pool


async def _ensure_schema(connection) -> None:
    """Ensure deposit table has required columns and indexes."""
    await connection.execute(
        "ALTER TABLE deposits ADD COLUMN IF NOT EXISTS gateway_order_id TEXT"
    )
    await connection.execute(
        "ALTER TABLE deposits ADD COLUMN IF NOT EXISTS payable_cents BIGINT DEFAULT 0"
    )
    await connection.execute(
        "ALTER TABLE deposits ADD COLUMN IF NOT EXISTS fee_cents BIGINT DEFAULT 0"
    )
    await connection.execute(
        "ALTER TABLE deposits ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ"
    )
    await connection.execute(
        "ALTER TABLE deposits ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()"
    )
    await connection.execute(
        "ALTER TABLE deposits ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ"
    )
    await connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS deposits_gateway_order_id_idx
        ON deposits (gateway_order_id)
        """
    )


async def create_deposit(
    *,
    user_id: int,
    amount_cents: int,
    fee_cents: int,
    payable_cents: int,
    method: str,
    gateway_order_id: str,
    expires_at: datetime | None,
) -> Dict[str, Any]:
    """Create a pending deposit entry tied to a Pakasir transaction."""
    pool = await get_pool()
    async with pool.acquire() as connection:
        await _ensure_schema(connection)
        row = await connection.fetchrow(
            """
            INSERT INTO deposits (
                user_id,
                amount_cents,
                method,
                status,
                reference,
                gateway_order_id,
                fee_cents,
                payable_cents,
                expires_at
            )
            VALUES ($1, $2, $3, 'pending', $4, $4, $5, $6, $7)
            RETURNING *;
            """,
            user_id,
            amount_cents,
            method,
            gateway_order_id,
            fee_cents,
            payable_cents,
            expires_at,
        )
    return dict(row)


async def update_deposit_status(
    gateway_order_id: str, status: str
) -> Optional[Dict[str, Any]]:
    """Update deposit status and return the deposit row."""
    pool = await get_pool()
    async with pool.acquire() as connection:
        await _ensure_schema(connection)
        row = await connection.fetchrow(
            """
            UPDATE deposits
            SET status = $2,
                updated_at = NOW(),
                completed_at = CASE
                    WHEN $2 IN ('completed', 'failed', 'expired', 'cancelled') THEN NOW()
                    ELSE completed_at
                END
            WHERE gateway_order_id = $1
            RETURNING *;
            """,
            gateway_order_id,
            status,
        )
    return dict(row) if row else None


async def get_deposit_by_gateway(gateway_order_id: str) -> Optional[Dict[str, Any]]:
    """Fetch deposit entry by gateway order id."""
    pool = await get_pool()
    async with pool.acquire() as connection:
        await _ensure_schema(connection)
        row = await connection.fetchrow(
            """
            SELECT d.*, u.telegram_id, u.username
            FROM deposits d
            JOIN users u ON d.user_id = u.id
            WHERE d.gateway_order_id = $1
            LIMIT 1;
            """,
            gateway_order_id,
        )
    return dict(row) if row else None


async def list_expired_deposits(limit: int = 10) -> List[Dict[str, Any]]:
    """Return pending deposits that have expired."""
    pool = await get_pool()
    async with pool.acquire() as connection:
        await _ensure_schema(connection)
        rows = await connection.fetch(
            """
            SELECT d.*, u.telegram_id, u.username
            FROM deposits d
            JOIN users u ON d.user_id = u.id
            WHERE d.status = 'pending'
              AND d.expires_at IS NOT NULL
              AND d.expires_at < NOW()
            ORDER BY d.expires_at ASC
            LIMIT $1;
            """,
            limit,
        )
    return [dict(row) for row in rows]
