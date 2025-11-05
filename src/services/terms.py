"""Service helpers for product terms (SNK) and customer submissions."""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional

from src.core.encryption import encrypt_text
from src.services.postgres import get_pool

logger = logging.getLogger(__name__)


async def _ensure_tables() -> None:
    """Create SNK related tables when missing."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS product_terms (
                product_id INTEGER PRIMARY KEY REFERENCES products(id) ON DELETE CASCADE,
                content TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS product_term_submissions (
                id BIGSERIAL PRIMARY KEY,
                order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                telegram_user_id BIGINT NOT NULL,
                message TEXT,
                media_file_id TEXT,
                media_type TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS product_term_notifications (
                id BIGSERIAL PRIMARY KEY,
                order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                telegram_user_id BIGINT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                sent_at TIMESTAMPTZ,
                responded_at TIMESTAMPTZ,
                UNIQUE (order_id, product_id)
            );
            """
        )


async def set_product_terms(*, product_id: int, content: str) -> None:
    """Create or update SNK content for a product."""
    await _ensure_tables()
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO product_terms (product_id, content)
            VALUES ($1, $2)
            ON CONFLICT (product_id)
            DO UPDATE SET content = EXCLUDED.content, updated_at = NOW();
            """,
            product_id,
            content,
        )
    logger.info("[snk] Updated product %s terms.", product_id)


async def clear_product_terms(product_id: int) -> None:
    """Remove SNK entry for a product."""
    await _ensure_tables()
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM product_terms WHERE product_id = $1;", product_id
        )
    logger.info("[snk] Cleared terms for product %s.", product_id)


async def get_product_terms(product_id: int) -> Optional[str]:
    """Return SNK content for a product when available."""
    await _ensure_tables()
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT content FROM product_terms WHERE product_id = $1 LIMIT 1;",
            product_id,
        )
    return row["content"] if row else None


async def fetch_terms_for_products(
    product_ids: Iterable[int],
) -> Dict[int, str]:
    """Return mapping product_id -> SNK content for given ids."""
    ids = list(dict.fromkeys(product_ids))
    if not ids:
        return {}
    await _ensure_tables()
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT product_id, content
            FROM product_terms
            WHERE product_id = ANY($1::INT[]);
            """,
            ids,
        )
    return {int(row["product_id"]): row["content"] for row in rows}


async def record_terms_submission(
    *,
    order_id: str,
    product_id: int,
    telegram_user_id: int,
    message: str | None,
    media_file_id: str | None,
    media_type: str | None,
) -> int:
    """Persist customer SNK submission for audit and follow-up."""
    await _ensure_tables()
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO product_term_submissions (
                order_id,
                product_id,
                telegram_user_id,
                message,
                media_file_id,
                media_type
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id;
            """,
            order_id,
            product_id,
            telegram_user_id,
            encrypt_text(message) if message else None,
            media_file_id,
            media_type,
        )
    submission_id = int(row["id"])
    logger.info(
        "[snk] Logged submission %s for order %s product %s.",
        submission_id,
        order_id,
        product_id,
    )
    return submission_id


async def schedule_terms_notifications(order_id: str) -> int:
    """Insert pending SNK notifications for order items that have terms."""
    await _ensure_tables()
    pool = await get_pool()
    inserted = 0
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                oi.product_id,
                pt.content,
                u.telegram_id AS user_telegram_id
            FROM order_items oi
            JOIN product_terms pt ON pt.product_id = oi.product_id
            JOIN orders o ON o.id = oi.order_id
            JOIN users u ON u.id = o.user_id
            WHERE oi.order_id = $1;
            """,
            order_id,
        )
        for row in rows:
            telegram_user_id = row.get("user_telegram_id")
            if telegram_user_id is None:
                logger.warning(
                    "[snk] Skip notification for order %s product %s, telegram_id missing.",
                    order_id,
                    row["product_id"],
                )
                continue
            result = await conn.execute(
                """
                INSERT INTO product_term_notifications (
                    order_id,
                    product_id,
                    telegram_user_id,
                    content
                )
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (order_id, product_id) DO NOTHING;
                """,
                order_id,
                row["product_id"],
                telegram_user_id,
                row["content"],
            )
            if result.endswith(" 1"):
                inserted += 1
    if inserted:
        logger.info(
            "[snk] Scheduled %s SNK notifications for order %s.", inserted, order_id
        )
    return inserted


async def list_pending_notifications(limit: int = 20) -> List[Dict[str, Any]]:
    """Return SNK notifications not yet sent."""
    await _ensure_tables()
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, order_id, product_id, telegram_user_id, content, created_at
            FROM product_term_notifications
            WHERE sent_at IS NULL
            ORDER BY created_at ASC
            LIMIT $1;
            """,
            limit,
        )
    return [dict(row) for row in rows]


async def mark_notification_sent(notification_id: int) -> None:
    """Mark SNK notification as delivered to customer."""
    await _ensure_tables()
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE product_term_notifications
            SET sent_at = NOW()
            WHERE id = $1;
            """,
            notification_id,
        )


async def mark_notification_responded(notification_id: int) -> None:
    """Mark SNK notification as responded by customer."""
    await _ensure_tables()
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE product_term_notifications
            SET responded_at = NOW()
            WHERE id = $1;
            """,
            notification_id,
        )


async def get_notification(notification_id: int) -> Optional[Dict[str, Any]]:
    """Fetch single SNK notification row."""
    await _ensure_tables()
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT *
            FROM product_term_notifications
            WHERE id = $1;
            """,
            notification_id,
        )
    return dict(row) if row else None


async def purge_old_submissions(retention_days: int) -> int:
    """Hapus submission SNK yang melampaui retention."""

    await _ensure_tables()
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            DELETE FROM product_term_submissions
            WHERE created_at < NOW() - ($1::TEXT || ' days')::INTERVAL;
            """,
            retention_days,
        )
    try:
        return int(result.split(" ")[1])
    except Exception:  # pragma: no cover - defensive
        return 0
