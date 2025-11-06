"""Persisted tracking for payment-related Telegram messages."""

from __future__ import annotations

from typing import Dict, List

import logging

from src.services.postgres import get_pool


logger = logging.getLogger(__name__)


async def _ensure_table() -> None:
    """Ensure storage table exists."""
    pool = await get_pool()
    async with pool.acquire() as connection:
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS payment_message_logs (
                id BIGSERIAL PRIMARY KEY,
                gateway_order_id TEXT NOT NULL,
                chat_id BIGINT NOT NULL,
                message_id BIGINT NOT NULL,
                role TEXT NOT NULL,
                message_kind TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )
        await connection.execute(
            """
            CREATE INDEX IF NOT EXISTS payment_message_logs_gateway_order_id_idx
            ON payment_message_logs (gateway_order_id);
            """
        )


async def record_payment_message(
    *,
    gateway_order_id: str,
    chat_id: int,
    message_id: int,
    role: str,
    message_kind: str,
) -> None:
    """Persist message metadata to enable follow-up edits or deletions."""
    await _ensure_table()
    pool = await get_pool()
    async with pool.acquire() as connection:
        await connection.execute(
            """
            INSERT INTO payment_message_logs (
                gateway_order_id,
                chat_id,
                message_id,
                role,
                message_kind
            )
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT DO NOTHING;
            """,
            gateway_order_id,
            chat_id,
            message_id,
            role,
            message_kind,
        )
    logger.debug(
        "[payment_message] Recorded %s message %s for %s",
        role,
        message_id,
        gateway_order_id,
    )


async def fetch_payment_messages(gateway_order_id: str) -> List[Dict[str, object]]:
    """Return stored message entries for a gateway order id."""
    await _ensure_table()
    pool = await get_pool()
    async with pool.acquire() as connection:
        rows = await connection.fetch(
            """
            SELECT chat_id, message_id, role, message_kind
            FROM payment_message_logs
            WHERE gateway_order_id = $1;
            """,
            gateway_order_id,
        )
    return [dict(row) for row in rows]


async def delete_payment_messages(gateway_order_id: str) -> None:
    """Remove stored entries after completion or cancellation."""
    await _ensure_table()
    pool = await get_pool()
    async with pool.acquire() as connection:
        await connection.execute(
            """
            DELETE FROM payment_message_logs
            WHERE gateway_order_id = $1;
            """,
            gateway_order_id,
        )
