"""Order service: CRUD untuk order dan order_items dengan audit."""

from __future__ import annotations

import logging
from typing import List, Dict, Any
from uuid import UUID

from src.services.postgres import get_pool
from src.services.terms import schedule_terms_notifications

logger = logging.getLogger(__name__)


async def list_orders_by_user(
    user_id: int, limit: int = 10
) -> List[Dict[str, Any]]:
    """
    List all orders for a specific user, sorted by most recent.

    Args:
        user_id: The user's internal database ID
        limit: Max number of orders to return

    Returns:
        List of orders with payment info
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                o.id,
                o.status,
                o.total_price_cents,
                o.created_at,
                p.status AS payment_status
            FROM orders o
            LEFT JOIN payments p ON p.order_id = o.id
            WHERE o.user_id = $1
            ORDER BY o.created_at DESC
            LIMIT $2;
            """,
            user_id,
            limit,
        )
    return [dict(row) for row in rows]


async def list_orders(limit: int = 50) -> List[Dict[str, Any]]:
    """
    List semua order, urut terbaru.

    Args:
        limit: Maksimal jumlah order yang dikembalikan

    Returns:
        List order dengan info user
    """
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


async def get_order(order_id: str | UUID) -> Dict[str, Any] | None:
    """
    Ambil detail order berdasarkan ID.

    Args:
        order_id: UUID order (string atau UUID object)

    Returns:
        Dict order atau None jika tidak ditemukan
    """
    # Convert to UUID if string
    if isinstance(order_id, str):
        try:
            order_id = UUID(order_id)
        except (ValueError, TypeError) as e:
            logger.warning("[order] Invalid order_id format: %s", order_id)
            return None

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT o.*, u.telegram_id, u.username
            FROM orders o
            JOIN users u ON o.user_id = u.id
            WHERE o.id = $1
            LIMIT 1;
            """,
            order_id,
        )
    return dict(row) if row else None


async def update_order_status(order_id: str | UUID, status: str) -> None:
    """
    Update status order.

    Args:
        order_id: UUID order (string atau UUID object)
        status: Status baru order

    Raises:
        ValueError: Jika order tidak ditemukan atau status invalid
    """
    # Convert to UUID if string
    if isinstance(order_id, str):
        try:
            order_id = UUID(order_id)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Format order_id tidak valid: {order_id}") from e

    # Validasi status
    valid_statuses = {"pending", "awaiting_payment", "paid", "cancelled", "expired"}
    if status not in valid_statuses:
        raise ValueError(
            f"Status '{status}' tidak valid. Status valid: {', '.join(valid_statuses)}"
        )

    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE orders
            SET status = $2, updated_at = NOW()
            WHERE id = $1;
            """,
            order_id,
            status,
        )

        if result == "UPDATE 0":
            raise ValueError(f"Order dengan ID {order_id} tidak ditemukan")

    logger.info("[order_status] Order %s di-set ke %s", order_id, status)

    # Schedule terms notifications jika order paid/completed
    normalized = status.strip().lower()
    if normalized in {"paid", "completed", "settled"}:
        await schedule_terms_notifications(str(order_id))


async def add_order_item(
    order_id: str | UUID, product_id: int, quantity: int, unit_price_cents: int
) -> int:
    """
    Tambah item ke order dengan validasi.

    Args:
        order_id: UUID order (string atau UUID object)
        product_id: ID produk
        quantity: Jumlah produk
        unit_price_cents: Harga satuan dalam cents

    Returns:
        ID order_item yang baru dibuat

    Raises:
        ValueError: Jika validasi gagal
    """
    # Convert to UUID if string
    if isinstance(order_id, str):
        try:
            order_id = UUID(order_id)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Format order_id tidak valid: {order_id}") from e

    # Validasi input
    if quantity <= 0:
        raise ValueError("Quantity harus lebih dari 0")

    if unit_price_cents < 0:
        raise ValueError("Harga tidak boleh negatif")

    pool = await get_pool()
    async with pool.acquire() as conn:
        # Validasi order exists
        order_exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM orders WHERE id = $1)", order_id
        )
        if not order_exists:
            raise ValueError(f"Order dengan ID {order_id} tidak ditemukan")

        # Validasi produk exists dan aktif
        product = await conn.fetchrow(
            """
            SELECT id, name, is_active, stock
            FROM products
            WHERE id = $1
            LIMIT 1;
            """,
            product_id,
        )

        if not product:
            raise ValueError(f"Produk dengan ID {product_id} tidak ditemukan")

        if not product["is_active"]:
            raise ValueError(
                f"Produk '{product['name']}' tidak aktif dan tidak dapat dipesan"
            )

        # Validasi stok (warning saja, tidak blocking)
        if product["stock"] < quantity:
            logger.warning(
                "[order_item] Product %s stok tidak cukup (%s < %s), tetap diproses",
                product_id,
                product["stock"],
                quantity,
            )

        # Insert order item
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

        order_item_id = row["id"]
        logger.info(
            "[order_item] Added item id=%s to order %s: product=%s qty=%s",
            order_item_id,
            order_id,
            product_id,
            quantity,
        )

        return order_item_id


async def ensure_order_can_transition(
    order_id: str | UUID,
    new_status: str,
    *,
    admin_id: int,
    note: str | None = None,
) -> None:
    """
    Validasi sebelum order berubah status.

    Jika status target adalah status "selesai" (paid/completed/settled),
    pastikan sudah ada pembayaran gateway yang sukses atau catatan manual.

    Args:
        order_id: UUID order (string atau UUID object)
        new_status: Status baru yang akan di-set
        admin_id: ID admin yang melakukan perubahan
        note: Catatan tambahan untuk verifikasi manual

    Raises:
        ValueError: Jika order tidak dapat transition ke status baru
    """
    # Convert to UUID if string
    if isinstance(order_id, str):
        try:
            order_id = UUID(order_id)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Format order_id tidak valid: {order_id}") from e

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

        # Create table if not exists
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS order_manual_verifications (
                id BIGSERIAL PRIMARY KEY,
                order_id UUID NOT NULL,
                admin_id BIGINT NOT NULL,
                note TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )

        # Record manual verification
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


async def get_last_order_for_user(telegram_id: int) -> Dict[str, Any] | None:
    """
    Fetch the latest order (and latest payment status) for given Telegram user.

    Args:
        telegram_id: Telegram user ID

    Returns:
        Dict order dengan info payment atau None
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            WITH target_user AS (
                SELECT id FROM users WHERE telegram_id = $1 LIMIT 1
            )
            SELECT
                o.id,
                o.status,
                o.total_price_cents,
                o.created_at,
                o.updated_at,
                p.gateway_order_id,
                p.status AS payment_status,
                p.updated_at AS payment_updated_at
            FROM orders o
            JOIN target_user tu ON o.user_id = tu.id
            LEFT JOIN LATERAL (
                SELECT gateway_order_id, status, updated_at
                FROM payments
                WHERE order_id = o.id
                ORDER BY updated_at DESC NULLS LAST
                LIMIT 1
            ) p ON TRUE
            ORDER BY o.created_at DESC
            LIMIT 1;
            """,
            telegram_id,
        )
    return dict(row) if row else None


async def list_order_items(order_id: str | UUID) -> List[Dict[str, Any]]:
    """
    Return items for a given order with product metadata.

    Args:
        order_id: UUID order (string atau UUID object)

    Returns:
        List order items dengan info produk
    """
    # Convert to UUID if string
    if isinstance(order_id, str):
        try:
            order_id = UUID(order_id)
        except (ValueError, TypeError) as e:
            logger.warning("[order_items] Invalid order_id format: %s", order_id)
            return []

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                oi.id,
                oi.product_id,
                oi.quantity,
                oi.unit_price_cents,
                oi.created_at,
                p.name AS product_name,
                p.code AS product_code,
                p.is_active AS product_is_active
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id = $1
            ORDER BY oi.id ASC;
            """,
            order_id,
        )
    return [dict(row) for row in rows]


async def delete_order_item(order_item_id: int) -> None:
    """
    Hapus order item.

    Args:
        order_item_id: ID order item

    Raises:
        ValueError: Jika order item tidak ditemukan
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM order_items WHERE id = $1;", order_item_id
        )

        if result == "DELETE 0":
            raise ValueError(f"Order item dengan ID {order_item_id} tidak ditemukan")

        logger.info("[order_item] Deleted order_item id=%s", order_item_id)


async def cancel_order(order_id: str | UUID, reason: str | None = None) -> None:
    """
    Cancel order dengan alasan.

    Args:
        order_id: UUID order (string atau UUID object)
        reason: Alasan cancel (opsional)

    Raises:
        ValueError: Jika order tidak dapat dicancel
    """
    # Convert to UUID if string
    if isinstance(order_id, str):
        try:
            order_id = UUID(order_id)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Format order_id tidak valid: {order_id}") from e

    pool = await get_pool()
    async with pool.acquire() as conn:
        # Check current status
        order = await conn.fetchrow(
            "SELECT id, status FROM orders WHERE id = $1 LIMIT 1;", order_id
        )

        if not order:
            raise ValueError(f"Order dengan ID {order_id} tidak ditemukan")

        if order["status"] in ("paid", "completed"):
            raise ValueError(
                f"Order dengan status '{order['status']}' tidak dapat dicancel. "
                "Gunakan fitur refund untuk order yang sudah dibayar."
            )

        # Update to cancelled
        await conn.execute(
            """
            UPDATE orders
            SET status = 'cancelled',
                metadata = metadata || jsonb_build_object('cancel_reason', $2, 'cancelled_at', NOW()),
                updated_at = NOW()
            WHERE id = $1;
            """,
            order_id,
            reason or "Dibatalkan oleh sistem",
        )

        logger.info(
            "[order] Cancelled order %s with reason: %s", order_id, reason or "N/A"
        )


async def get_order_stats() -> Dict[str, Any]:
    """
    Ambil statistik order.

    Returns:
        Dict dengan berbagai statistik order
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        stats = await conn.fetchrow(
            """
            SELECT
                COUNT(*) as total_orders,
                COUNT(*) FILTER (WHERE status = 'pending') as pending_count,
                COUNT(*) FILTER (WHERE status = 'awaiting_payment') as awaiting_payment_count,
                COUNT(*) FILTER (WHERE status = 'paid') as paid_count,
                COUNT(*) FILTER (WHERE status = 'cancelled') as cancelled_count,
                COUNT(*) FILTER (WHERE status = 'expired') as expired_count,
                COALESCE(SUM(total_price_cents) FILTER (WHERE status = 'paid'), 0) as total_revenue_cents,
                COALESCE(AVG(total_price_cents) FILTER (WHERE status = 'paid'), 0) as avg_order_value_cents
            FROM orders;
            """
        )

    return dict(stats) if stats else {}
