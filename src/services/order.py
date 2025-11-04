"""Order service: CRUD untuk order dan order_items dengan audit."""

from __future__ import annotations

import logging
from typing import List, Dict, Any

from src.services.postgres import get_pool

logger = logging.getLogger(__name__)


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


async def update_order_status(order_id: int | str, status: str) -> None:
    """Update status order."""
    order_id_int = int(order_id)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE orders
            SET status = $2, updated_at = NOW()
            WHERE id = $1;
            """,
            order_id_int,
            status,
        )
    logger.info("[order_status] Order %s di-set ke %s", order_id_int, status)


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


async def ensure_order_can_transition(
    order_id: int,
    new_status: str,
    *,
    admin_id: int,
    note: str | None = None,
) -> None:
    """
    Validasi sebelum order berubah status.

    Jika status target adalah status "selesai" (paid/completed/settled),
    pastikan sudah ada pembayaran gateway yang sukses atau catatan manual.
    """

    sensitive_statuses = {"paid", "completed", "settled"}
    normalized_status = new_status.strip().lower()
    if normalized_status not in sensitive_statuses:
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        order_row = await conn.fetchrow(
            "SELECT id, total_price_cents FROM orders WHERE id = $1 LIMIT 1;",
            order_id,
        )
        if order_row is None:
            raise ValueError(f"Order {order_id} tidak ditemukan.")

        payment_row = await conn.fetchrow(
            """
            SELECT status, amount_cents, method
            FROM payments
            WHERE order_id = $1
            ORDER BY updated_at DESC
            LIMIT 1;
            """,
            order_id,
        )

        order_total = int(order_row.get("total_price_cents") or 0)

        if payment_row and payment_row.get("status") == "completed":
            paid_amount = int(payment_row.get("amount_cents") or 0)
            if paid_amount != order_total:
                raise ValueError(
                    "Nominal pembayaran berbeda dengan total order. Tolong cek ulang sebelum menandai selesai."
                )
            logger.info(
                "[order_check] Pembayaran order %s sudah terverifikasi otomatis.",
                order_id,
            )
            return

        if not note:
            raise ValueError(
                "Order belum memiliki pembayaran terverifikasi. Sertakan catatan singkat (mis. nomor resi transfer)."
            )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS order_manual_verifications (
                id BIGSERIAL PRIMARY KEY,
                order_id BIGINT NOT NULL,
                admin_id BIGINT NOT NULL,
                note TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )
        await conn.execute(
            """
            INSERT INTO order_manual_verifications (order_id, admin_id, note)
            VALUES ($1, $2, $3);
            """,
            order_id,
            admin_id,
            note,
        )
        logger.info(
            "[manual_payment] Admin %s mencatat verifikasi manual untuk order %s: %s",
            admin_id,
            order_id,
            note,
        )
