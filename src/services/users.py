"""User related database helpers."""

from __future__ import annotations

from typing import Any

from src.services.postgres import get_pool


async def upsert_user(
    *,
    telegram_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
) -> int:
    """Insert or update a user and return internal ID."""
    pool = await get_pool()
    async with pool.acquire() as connection:
        row = await connection.fetchrow(
            """
            INSERT INTO users (telegram_id, username, first_name, last_name)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (telegram_id)
            DO UPDATE SET
                username = EXCLUDED.username,
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                updated_at = NOW()
            RETURNING id;
            """,
            telegram_id,
            username,
            first_name,
            last_name,
        )
    if row is None:
        raise RuntimeError("Failed to upsert user.")
    return int(row["id"])


async def update_balance(user_id: int, amount_cents: int) -> None:
    """Adjust user balance by `amount_cents`."""
    pool = await get_pool()
    await pool.execute(
        """
        UPDATE users
        SET balance_cents = balance_cents + $2,
            updated_at = NOW()
        WHERE id = $1;
        """,
        user_id,
        amount_cents,
    )
