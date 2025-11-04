"""Service untuk CRUD template pesan balasan bot (reply_templates)."""

from __future__ import annotations

from typing import List, Dict, Any, Optional
from src.services.postgres import get_pool


async def add_template(label: str, content: str, is_active: bool = True) -> int:
    """Tambah template pesan baru ke database."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO reply_templates (label, content, is_active)
            VALUES ($1, $2, $3)
            RETURNING id;
            """,
            label,
            content,
            is_active,
        )
    return row["id"]


async def edit_template(template_id: int, **fields) -> None:
    """Edit template pesan di database."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        sets = ", ".join([f"{k} = ${i + 2}" for i, k in enumerate(fields.keys())])
        values = [template_id] + list(fields.values())
        await conn.execute(
            f"UPDATE reply_templates SET {sets}, updated_at = NOW() WHERE id = $1;",
            *values,
        )


async def delete_template(template_id: int) -> None:
    """Hapus template pesan dari database."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM reply_templates WHERE id = $1;", template_id)


async def list_templates(limit: int = 50) -> List[Dict[str, Any]]:
    """List semua template pesan aktif."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM reply_templates
            WHERE is_active = TRUE
            ORDER BY updated_at DESC
            LIMIT $1;
            """,
            limit,
        )
    return [dict(row) for row in rows]


async def get_template(label: str) -> Optional[Dict[str, Any]]:
    """Ambil template pesan berdasarkan label."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM reply_templates
            WHERE label = $1 AND is_active = TRUE
            LIMIT 1;
            """,
            label,
        )
    return dict(row) if row else None
