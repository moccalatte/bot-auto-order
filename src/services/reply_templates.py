"""Service untuk CRUD template pesan balasan bot (reply_templates)."""

from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional
from src.services.postgres import get_pool

logger = logging.getLogger(__name__)


async def add_template(label: str, content: str, is_active: bool = True) -> int:
    """
    Tambah template pesan baru ke database.

    Args:
        label: Label unik template
        content: Konten template
        is_active: Status aktif template

    Returns:
        ID template yang baru dibuat

    Raises:
        ValueError: Jika validasi gagal
    """
    # Validasi input
    if not label or not label.strip():
        raise ValueError("Label template tidak boleh kosong")

    if not content or not content.strip():
        raise ValueError("Konten template tidak boleh kosong")

    # Check duplikat label
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM reply_templates WHERE label = $1)",
            label.strip(),
        )
        if existing:
            raise ValueError(f"Template dengan label '{label}' sudah ada")

        try:
            row = await conn.fetchrow(
                """
                INSERT INTO reply_templates (label, content, is_active)
                VALUES ($1, $2, $3)
                RETURNING id;
                """,
                label.strip(),
                content.strip(),
                is_active,
            )
            template_id = row["id"]
            logger.info(
                "[reply_templates] Added template id=%s label=%s", template_id, label
            )
            return template_id
        except Exception as e:
            error_msg = str(e)
            if "duplicate key" in error_msg.lower():
                raise ValueError(f"Template dengan label '{label}' sudah ada") from e
            raise


async def edit_template(template_id: int, **fields) -> None:
    """
    Edit template pesan di database.

    Args:
        template_id: ID template yang akan diedit
        **fields: Field yang akan diupdate

    Raises:
        ValueError: Jika validasi gagal
    """
    if not fields:
        raise ValueError("Tidak ada field yang akan diupdate")

    # Validasi data input
    if "label" in fields:
        if not fields["label"] or not fields["label"].strip():
            raise ValueError("Label template tidak boleh kosong")
        fields["label"] = fields["label"].strip()

        # Check duplikat label
        pool = await get_pool()
        async with pool.acquire() as conn:
            existing = await conn.fetchval(
                """
                SELECT EXISTS(
                    SELECT 1 FROM reply_templates
                    WHERE label = $1 AND id != $2
                )
                """,
                fields["label"],
                template_id,
            )
            if existing:
                raise ValueError(f"Template dengan label '{fields['label']}' sudah ada")

    if "content" in fields:
        if not fields["content"] or not fields["content"].strip():
            raise ValueError("Konten template tidak boleh kosong")
        fields["content"] = fields["content"].strip()

    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            sets = ", ".join([f"{k} = ${i + 2}" for i, k in enumerate(fields.keys())])
            values = [template_id] + list(fields.values())
            result = await conn.execute(
                f"UPDATE reply_templates SET {sets}, updated_at = NOW() WHERE id = $1;",
                *values,
            )

            if result == "UPDATE 0":
                raise ValueError(f"Template dengan ID {template_id} tidak ditemukan")

            logger.info(
                "[reply_templates] Updated template id=%s fields=%s",
                template_id,
                list(fields.keys()),
            )
        except ValueError:
            raise
        except Exception as e:
            error_msg = str(e)
            if "duplicate key" in error_msg.lower():
                raise ValueError(
                    f"Template dengan label '{fields.get('label')}' sudah ada"
                ) from e
            raise


async def delete_template(template_id: int) -> None:
    """
    Hapus template pesan dari database.

    Args:
        template_id: ID template yang akan dihapus

    Raises:
        ValueError: Jika template tidak ditemukan
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM reply_templates WHERE id = $1;", template_id
        )

        if result == "DELETE 0":
            raise ValueError(f"Template dengan ID {template_id} tidak ditemukan")

        logger.info("[reply_templates] Deleted template id=%s", template_id)


async def list_templates(
    limit: int = 50, include_inactive: bool = False
) -> List[Dict[str, Any]]:
    """
    List template pesan dengan filter.

    Args:
        limit: Maksimal jumlah template yang dikembalikan
        include_inactive: Apakah include template yang tidak aktif

    Returns:
        List template
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        if include_inactive:
            query = """
                SELECT * FROM reply_templates
                ORDER BY updated_at DESC
                LIMIT $1;
            """
        else:
            query = """
                SELECT * FROM reply_templates
                WHERE is_active = TRUE
                ORDER BY updated_at DESC
                LIMIT $1;
            """

        rows = await conn.fetch(query, limit)
    return [dict(row) for row in rows]


async def get_template(label: str) -> Optional[Dict[str, Any]]:
    """
    Ambil template pesan berdasarkan label.

    Args:
        label: Label template

    Returns:
        Dict template atau None jika tidak ditemukan
    """
    if not label or not label.strip():
        return None

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM reply_templates
            WHERE label = $1 AND is_active = TRUE
            LIMIT 1;
            """,
            label.strip(),
        )
    return dict(row) if row else None


async def get_template_by_id(template_id: int) -> Optional[Dict[str, Any]]:
    """
    Ambil template pesan berdasarkan ID.

    Args:
        template_id: ID template

    Returns:
        Dict template atau None jika tidak ditemukan
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM reply_templates
            WHERE id = $1
            LIMIT 1;
            """,
            template_id,
        )
    return dict(row) if row else None


async def template_exists(label: str) -> bool:
    """
    Check apakah template dengan label tertentu sudah ada.

    Args:
        label: Label template

    Returns:
        True jika template ada
    """
    if not label or not label.strip():
        return False

    pool = await get_pool()
    async with pool.acquire() as conn:
        exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM reply_templates WHERE label = $1)",
            label.strip(),
        )
    return bool(exists)


async def activate_template(template_id: int) -> None:
    """
    Aktifkan template.

    Args:
        template_id: ID template

    Raises:
        ValueError: Jika template tidak ditemukan
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE reply_templates
            SET is_active = TRUE, updated_at = NOW()
            WHERE id = $1;
            """,
            template_id,
        )

        if result == "UPDATE 0":
            raise ValueError(f"Template dengan ID {template_id} tidak ditemukan")

        logger.info("[reply_templates] Activated template id=%s", template_id)


async def deactivate_template(template_id: int) -> None:
    """
    Nonaktifkan template.

    Args:
        template_id: ID template

    Raises:
        ValueError: Jika template tidak ditemukan
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE reply_templates
            SET is_active = FALSE, updated_at = NOW()
            WHERE id = $1;
            """,
            template_id,
        )

        if result == "UPDATE 0":
            raise ValueError(f"Template dengan ID {template_id} tidak ditemukan")

        logger.info("[reply_templates] Deactivated template id=%s", template_id)
