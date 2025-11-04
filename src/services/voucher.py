"""Service untuk CRUD voucher/kupon diskon (coupons)."""

from __future__ import annotations

from typing import List, Dict, Any, Optional
from datetime import datetime
from src.services.postgres import get_pool


async def add_voucher(
    code: str,
    description: str,
    discount_type: str,
    discount_value: int,
    max_uses: int = None,
    valid_from: datetime = None,
    valid_until: datetime = None,
) -> int:
    """Tambah voucher baru ke database."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO coupons (code, description, discount_type, discount_value, max_uses, valid_from, valid_until)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id;
            """,
            code,
            description,
            discount_type,
            discount_value,
            max_uses,
            valid_from,
            valid_until,
        )
    return row["id"]


async def edit_voucher(voucher_id: int, **fields) -> None:
    """Edit voucher di database."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        sets = ", ".join([f"{k} = ${i + 2}" for i, k in enumerate(fields.keys())])
        values = [voucher_id] + list(fields.values())
        await conn.execute(
            f"UPDATE coupons SET {sets}, updated_at = NOW() WHERE id = $1;",
            *values,
        )


async def delete_voucher(voucher_id: int) -> None:
    """Hapus voucher dari database."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM coupons WHERE id = $1;", voucher_id)


async def list_vouchers(limit: int = 50) -> List[Dict[str, Any]]:
    """List semua voucher aktif."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM coupons
            WHERE (valid_until IS NULL OR valid_until > NOW())
            ORDER BY updated_at DESC
            LIMIT $1;
            """,
            limit,
        )
    return [dict(row) for row in rows]


async def get_voucher(code: str) -> Optional[Dict[str, Any]]:
    """Ambil voucher berdasarkan kode."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM coupons
            WHERE code = $1
            AND (valid_until IS NULL OR valid_until > NOW())
            LIMIT 1;
            """,
            code,
        )
    return dict(row) if row else None
