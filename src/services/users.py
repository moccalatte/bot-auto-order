"""User related database helpers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

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


async def _ensure_profile_columns(connection) -> None:
    """Ensure optional profile columns exist."""
    await connection.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS balance_cents BIGINT DEFAULT 0;"
    )
    await connection.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS bank_id TEXT;")
    await connection.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE;"
    )
    await connection.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name TEXT;"
    )
    await connection.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS whatsapp_number TEXT;"
    )


async def get_user_profile(telegram_id: int) -> Optional[Dict[str, Any]]:
    """Get extended profile info for a Telegram user."""
    pool = await get_pool()
    async with pool.acquire() as connection:
        await _ensure_profile_columns(connection)
        row = await connection.fetchrow(
            """
            SELECT
                telegram_id,
                username,
                first_name,
                last_name,
                balance_cents,
                bank_id,
                is_verified,
                display_name,
                whatsapp_number
            FROM users
            WHERE telegram_id = $1
            LIMIT 1;
            """,
            telegram_id,
        )
    return dict(row) if row else None


async def get_user_by_telegram_id(telegram_id: int) -> Dict[str, Any] | None:
    """Get full user record by Telegram ID."""
    pool = await get_pool()
    async with pool.acquire() as connection:
        row = await connection.fetchrow(
            """
            SELECT *
            FROM users
            WHERE telegram_id = $1
            LIMIT 1;
            """,
            telegram_id,
        )
    return dict(row) if row else None


async def update_user_profile(
    telegram_id: int,
    *,
    display_name: Optional[str] = None,
    whatsapp_number: Optional[str] = None,
) -> None:
    """Update custom profile fields for a Telegram user."""
    fields = []
    values: List[Any] = []
    if display_name is not None:
        fields.append("display_name = $%d" % (len(values) + 2))
        values.append(display_name)
    if whatsapp_number is not None:
        fields.append("whatsapp_number = $%d" % (len(values) + 2))
        values.append(whatsapp_number)
    if not fields:
        return

    pool = await get_pool()
    async with pool.acquire() as connection:
        await _ensure_profile_columns(connection)
        await connection.execute(
            f"""
            UPDATE users
            SET {", ".join(fields)},
                updated_at = NOW()
            WHERE telegram_id = $1;
            """,
            telegram_id,
            *values,
        )


async def list_users(limit: int = 50) -> list:
    """List semua user."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_blocked BOOLEAN DEFAULT FALSE;"
        )
        await conn.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS bot_blocked BOOLEAN DEFAULT FALSE;"
        )
        rows = await conn.fetch(
            "SELECT * FROM users ORDER BY created_at DESC LIMIT $1;", limit
        )
    return [dict(row) for row in rows]


async def block_user(user_id: int) -> None:
    """Blokir user."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_blocked BOOLEAN DEFAULT FALSE;"
        )
        await conn.execute(
            """
            UPDATE users
            SET is_blocked = TRUE,
                updated_at = NOW()
            WHERE id = $1;
            """,
            user_id,
        )


async def unblock_user(user_id: int) -> None:
    """Unblokir user."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_blocked BOOLEAN DEFAULT FALSE;"
        )
        await conn.execute(
            """
            UPDATE users
            SET is_blocked = FALSE,
                updated_at = NOW()
            WHERE id = $1;
            """,
            user_id,
        )


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


async def is_user_blocked(
    *,
    user_id: int | None = None,
    telegram_id: int | None = None,
) -> bool:
    """Check whether user is blocked."""
    if user_id is None and telegram_id is None:
        raise ValueError("Provide user_id atau telegram_id.")
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_blocked BOOLEAN DEFAULT FALSE;"
        )
        if user_id is not None:
            row = await conn.fetchrow(
                "SELECT is_blocked FROM users WHERE id = $1 LIMIT 1;", user_id
            )
        else:
            row = await conn.fetchrow(
                "SELECT is_blocked FROM users WHERE telegram_id = $1 LIMIT 1;",
                telegram_id,
            )
    return bool(row["is_blocked"]) if row else False


async def list_broadcast_targets() -> List[Dict[str, Any]]:
    """Return Telegram IDs that should receive broadcast (no blocked users)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_blocked BOOLEAN DEFAULT FALSE;"
        )
        await conn.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS bot_blocked BOOLEAN DEFAULT FALSE;"
        )
        rows = await conn.fetch(
            """
            SELECT id, telegram_id
            FROM users
            WHERE COALESCE(is_blocked, FALSE) = FALSE
              AND COALESCE(bot_blocked, FALSE) = FALSE;
            """
        )
    return [dict(row) for row in rows]


async def mark_user_bot_blocked(telegram_id: int, *, blocked: bool = True) -> None:
    """Mark that user has blocked the bot to skip future broadcasts."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS bot_blocked BOOLEAN DEFAULT FALSE;"
        )
        await conn.execute(
            """
            UPDATE users
            SET bot_blocked = $2,
                updated_at = NOW()
            WHERE telegram_id = $1;
            """,
            telegram_id,
            blocked,
        )
