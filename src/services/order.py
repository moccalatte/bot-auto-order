"""Order service: CRUD untuk order dan order_items."""

from __future__ import annotations

from typing import List, Dict, Any
from src.services.postgres import get_pool


async def list_orders(limit: int = 50) -> List[Dict[str, Any]]:
    """List semua order, urut terbaru."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT o.*, u.telegram_id, u.username
            FROM orders o
            JOIN users u ON o.user_id = u.id
            ORDER BY o.created_at DESC
            LIMIT $1;
            """,
            limit,
        )
    return [dict(row) for row in rows]


async def update_order_status(order_id: str, status: str) -> None:
    """Update status order."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE orders
            SET status = $2, updated_at = NOW()
            WHERE id = $1;
            """,
            order_id,
            status,
        )


async def add_order_item(
    order_id: str, product_id: int, quantity: int, unit_price_cents: int
) -> int:
    """Tambah item ke order."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO order_items (order_id, product_id, quantity, unit_price_cents)
            VALUES ($1, $2, $3, $4)
            RETURNING id;
            """,
            order_id,
            product_id,
            quantity,
            unit_price_cents,
        )
    return row["id"]
