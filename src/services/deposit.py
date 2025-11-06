"""Helpers for managing customer deposits."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.services.postgres import get_pool

logger = logging.getLogger(__name__)


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
        WHERE gateway_order_id IS NOT NULL
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
    """
    Create a pending deposit entry tied to a Pakasir transaction.

    Args:
        user_id: ID user yang melakukan deposit
        amount_cents: Jumlah deposit dalam cents
        fee_cents: Biaya admin dalam cents
        payable_cents: Total yang harus dibayar (amount + fee) dalam cents
        method: Metode pembayaran
        gateway_order_id: ID order dari payment gateway (WAJIB)
        expires_at: Waktu kadaluarsa pembayaran

    Returns:
        Dict deposit yang baru dibuat

    Raises:
        ValueError: Jika validasi gagal
    """
    # Validasi input
    if not gateway_order_id or not gateway_order_id.strip():
        raise ValueError("gateway_order_id tidak boleh kosong")

    if amount_cents <= 0:
        raise ValueError("Jumlah deposit harus lebih dari 0")

    if fee_cents < 0:
        raise ValueError("Fee tidak boleh negatif")

    if payable_cents < amount_cents:
        raise ValueError("Payable harus lebih besar atau sama dengan amount")

    if not method or not method.strip():
        raise ValueError("Method tidak boleh kosong")

    pool = await get_pool()
    async with pool.acquire() as connection:
        await _ensure_schema(connection)

        # Check if user exists
        user_exists = await connection.fetchval(
            "SELECT EXISTS(SELECT 1 FROM users WHERE id = $1)", user_id
        )
        if not user_exists:
            raise ValueError(f"User dengan ID {user_id} tidak ditemukan")

        # Check for duplicate gateway_order_id
        duplicate_exists = await connection.fetchval(
            """
            SELECT EXISTS(
                SELECT 1 FROM deposits
                WHERE gateway_order_id = $1
            )
            """,
            gateway_order_id.strip(),
        )
        if duplicate_exists:
            raise ValueError(
                f"Deposit dengan gateway_order_id '{gateway_order_id}' sudah ada"
            )

        try:
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
                method.strip(),
                gateway_order_id.strip(),
                fee_cents,
                payable_cents,
                expires_at,
            )

            deposit_id = row["id"]
            logger.info(
                "[deposit] Created deposit id=%s for user=%s amount=%s gateway=%s",
                deposit_id,
                user_id,
                amount_cents,
                gateway_order_id,
            )

            return dict(row)

        except Exception as e:
            error_msg = str(e)
            if "duplicate key" in error_msg.lower():
                raise ValueError(
                    f"Deposit dengan gateway_order_id '{gateway_order_id}' sudah ada"
                ) from e
            raise


async def create_manual_deposit(
    *,
    user_id: int,
    amount_cents: int,
    method: str,
    notes: str | None = None,
    admin_id: int | None = None,
) -> Dict[str, Any]:
    """
    Create a manual deposit (by admin) without payment gateway.

    Args:
        user_id: ID user yang menerima deposit
        amount_cents: Jumlah deposit dalam cents
        method: Metode pembayaran (misal: "bank_transfer", "cash")
        notes: Catatan tambahan
        admin_id: ID admin yang membuat deposit

    Returns:
        Dict deposit yang baru dibuat

    Raises:
        ValueError: Jika validasi gagal
    """
    # Validasi input
    if amount_cents <= 0:
        raise ValueError("Jumlah deposit harus lebih dari 0")

    if not method or not method.strip():
        raise ValueError("Method tidak boleh kosong")

    pool = await get_pool()
    async with pool.acquire() as connection:
        await _ensure_schema(connection)

        # Check if user exists
        user_exists = await connection.fetchval(
            "SELECT EXISTS(SELECT 1 FROM users WHERE id = $1)", user_id
        )
        if not user_exists:
            raise ValueError(f"User dengan ID {user_id} tidak ditemukan")

        row = await connection.fetchrow(
            """
            INSERT INTO deposits (
                user_id,
                amount_cents,
                method,
                status,
                created_by_admin,
                notes
            )
            VALUES ($1, $2, $3, 'completed', TRUE, $4)
            RETURNING *;
            """,
            user_id,
            amount_cents,
            method.strip(),
            notes or f"Manual deposit by admin {admin_id or 'unknown'}",
        )

        deposit_id = row["id"]
        logger.info(
            "[deposit] Created manual deposit id=%s for user=%s amount=%s by admin=%s",
            deposit_id,
            user_id,
            amount_cents,
            admin_id or "unknown",
        )

        return dict(row)


async def update_deposit_status(
    gateway_order_id: str, status: str
) -> Optional[Dict[str, Any]]:
    """
    Update deposit status and return the deposit row.

    Args:
        gateway_order_id: Gateway order ID
        status: Status baru ('pending', 'completed', 'failed', 'expired', 'cancelled')

    Returns:
        Dict deposit atau None jika tidak ditemukan

    Raises:
        ValueError: Jika validasi gagal
    """
    if not gateway_order_id or not gateway_order_id.strip():
        raise ValueError("gateway_order_id tidak boleh kosong")

    valid_statuses = {"pending", "completed", "failed", "expired", "cancelled"}
    if status not in valid_statuses:
        raise ValueError(
            f"Status '{status}' tidak valid. Status valid: {', '.join(valid_statuses)}"
        )

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
            gateway_order_id.strip(),
            status,
        )

        if row:
            logger.info(
                "[deposit] Updated deposit gateway=%s to status=%s",
                gateway_order_id,
                status,
            )

        return dict(row) if row else None


async def get_deposit_by_gateway(gateway_order_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch deposit entry by gateway order id.

    Args:
        gateway_order_id: Gateway order ID

    Returns:
        Dict deposit dengan info user atau None jika tidak ditemukan
    """
    if not gateway_order_id or not gateway_order_id.strip():
        return None

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
            gateway_order_id.strip(),
        )
    return dict(row) if row else None


async def get_deposit_by_id(deposit_id: int) -> Optional[Dict[str, Any]]:
    """
    Fetch deposit entry by deposit ID.

    Args:
        deposit_id: Deposit ID

    Returns:
        Dict deposit dengan info user atau None jika tidak ditemukan
    """
    pool = await get_pool()
    async with pool.acquire() as connection:
        await _ensure_schema(connection)
        row = await connection.fetchrow(
            """
            SELECT d.*, u.telegram_id, u.username
            FROM deposits d
            JOIN users u ON d.user_id = u.id
            WHERE d.id = $1
            LIMIT 1;
            """,
            deposit_id,
        )
    return dict(row) if row else None


async def list_user_deposits(
    user_id: int, limit: int = 50, include_pending: bool = True
) -> List[Dict[str, Any]]:
    """
    List deposits untuk user tertentu.

    Args:
        user_id: ID user
        limit: Maksimal jumlah deposit yang dikembalikan
        include_pending: Apakah include pending deposits

    Returns:
        List deposits
    """
    pool = await get_pool()
    async with pool.acquire() as connection:
        await _ensure_schema(connection)

        if include_pending:
            query = """
                SELECT d.*, u.telegram_id, u.username
                FROM deposits d
                JOIN users u ON d.user_id = u.id
                WHERE d.user_id = $1
                ORDER BY d.created_at DESC
                LIMIT $2;
            """
        else:
            query = """
                SELECT d.*, u.telegram_id, u.username
                FROM deposits d
                JOIN users u ON d.user_id = u.id
                WHERE d.user_id = $1 AND d.status != 'pending'
                ORDER BY d.created_at DESC
                LIMIT $2;
            """

        rows = await connection.fetch(query, user_id, limit)

    return [dict(row) for row in rows]


async def list_expired_deposits(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Return pending deposits that have expired.

    Args:
        limit: Maksimal jumlah deposit yang dikembalikan

    Returns:
        List expired deposits
    """
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


async def expire_old_deposits() -> int:
    """
    Mark expired pending deposits as 'expired'.

    Returns:
        Jumlah deposits yang di-expire
    """
    pool = await get_pool()
    async with pool.acquire() as connection:
        await _ensure_schema(connection)
        result = await connection.execute(
            """
            UPDATE deposits
            SET status = 'expired',
                updated_at = NOW(),
                completed_at = NOW()
            WHERE status = 'pending'
              AND expires_at IS NOT NULL
              AND expires_at < NOW();
            """
        )

        # Extract number of rows updated
        try:
            expired_count = int(result.split(" ")[1])
        except (IndexError, ValueError):
            expired_count = 0

        if expired_count > 0:
            logger.info("[deposit] Expired %s old deposits", expired_count)

        return expired_count


async def get_deposit_stats() -> Dict[str, Any]:
    """
    Ambil statistik deposit.

    Returns:
        Dict dengan berbagai statistik deposit
    """
    pool = await get_pool()
    async with pool.acquire() as connection:
        await _ensure_schema(connection)
        stats = await connection.fetchrow(
            """
            SELECT
                COUNT(*) as total_deposits,
                COUNT(*) FILTER (WHERE status = 'pending') as pending_count,
                COUNT(*) FILTER (WHERE status = 'completed') as completed_count,
                COUNT(*) FILTER (WHERE status = 'failed') as failed_count,
                COUNT(*) FILTER (WHERE status = 'expired') as expired_count,
                COUNT(*) FILTER (WHERE status = 'cancelled') as cancelled_count,
                COALESCE(SUM(amount_cents) FILTER (WHERE status = 'completed'), 0) as total_amount_cents,
                COALESCE(AVG(amount_cents) FILTER (WHERE status = 'completed'), 0) as avg_amount_cents,
                COUNT(*) FILTER (WHERE created_by_admin = TRUE) as manual_deposits_count,
                COALESCE(SUM(amount_cents) FILTER (WHERE created_by_admin = TRUE AND status = 'completed'), 0) as manual_deposits_total_cents
            FROM deposits;
            """
        )

    return dict(stats) if stats else {}


async def delete_deposit(deposit_id: int) -> None:
    """
    Hapus deposit (hanya untuk deposit pending yang belum diproses).

    Args:
        deposit_id: ID deposit

    Raises:
        ValueError: Jika deposit tidak dapat dihapus
    """
    pool = await get_pool()
    async with pool.acquire() as connection:
        await _ensure_schema(connection)

        # Check current status
        deposit = await connection.fetchrow(
            "SELECT id, status FROM deposits WHERE id = $1 LIMIT 1;", deposit_id
        )

        if not deposit:
            raise ValueError(f"Deposit dengan ID {deposit_id} tidak ditemukan")

        if deposit["status"] == "completed":
            raise ValueError(
                "Deposit yang sudah completed tidak dapat dihapus. "
                "Gunakan fitur refund jika perlu."
            )

        result = await connection.execute(
            "DELETE FROM deposits WHERE id = $1;", deposit_id
        )

        if result == "DELETE 0":
            raise ValueError(f"Deposit dengan ID {deposit_id} tidak ditemukan")

        logger.info("[deposit] Deleted deposit id=%s", deposit_id)


async def cancel_deposit(deposit_id: int, reason: str | None = None) -> Dict[str, Any]:
    """
    Cancel deposit dengan alasan.

    Args:
        deposit_id: ID deposit
        reason: Alasan cancel (opsional)

    Returns:
        Dict deposit yang di-cancel

    Raises:
        ValueError: Jika deposit tidak dapat dicancel
    """
    pool = await get_pool()
    async with pool.acquire() as connection:
        await _ensure_schema(connection)

        # Check current status
        deposit = await connection.fetchrow(
            "SELECT id, status, gateway_order_id FROM deposits WHERE id = $1 LIMIT 1;",
            deposit_id,
        )

        if not deposit:
            raise ValueError(f"Deposit dengan ID {deposit_id} tidak ditemukan")

        if deposit["status"] == "completed":
            raise ValueError(
                "Deposit yang sudah completed tidak dapat dicancel. "
                "Gunakan fitur refund jika perlu."
            )

        if deposit["status"] in ("cancelled", "expired", "failed"):
            raise ValueError(
                f"Deposit dengan status '{deposit['status']}' sudah tidak aktif"
            )

        # Update to cancelled
        row = await connection.fetchrow(
            """
            UPDATE deposits
            SET status = 'cancelled',
                notes = COALESCE(notes, '') || ' | Cancelled: ' || $2,
                updated_at = NOW(),
                completed_at = NOW()
            WHERE id = $1
            RETURNING *;
            """,
            deposit_id,
            reason or "Dibatalkan oleh sistem",
        )

        logger.info(
            "[deposit] Cancelled deposit id=%s gateway=%s reason=%s",
            deposit_id,
            deposit["gateway_order_id"] or "N/A",
            reason or "N/A",
        )

        return dict(row) if row else {}
