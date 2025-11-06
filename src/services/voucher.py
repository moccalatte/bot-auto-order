"""Service untuk CRUD voucher/kupon diskon (coupons)."""

from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from src.services.postgres import get_pool

logger = logging.getLogger(__name__)


async def add_voucher(
    code: str,
    description: str,
    discount_type: str,
    discount_value: int,
    max_uses: int = None,
    valid_from: datetime = None,
    valid_until: datetime = None,
) -> int:
    """
    Tambah voucher baru ke database.

    Args:
        code: Kode unik voucher
        description: Deskripsi voucher
        discount_type: Tipe diskon ('percent' atau 'flat')
        discount_value: Nilai diskon (persen atau nominal dalam cents)
        max_uses: Maksimal penggunaan (None = unlimited)
        valid_from: Tanggal mulai berlaku (None = sekarang)
        valid_until: Tanggal berakhir (None = tidak ada batas)

    Returns:
        ID voucher yang baru dibuat

    Raises:
        ValueError: Jika validasi gagal
    """
    # Validasi input
    if not code or not code.strip():
        raise ValueError("Kode voucher tidak boleh kosong")

    if discount_type not in ("percent", "flat"):
        raise ValueError("Tipe diskon harus 'percent' atau 'flat'")

    if discount_value <= 0:
        raise ValueError("Nilai diskon harus lebih dari 0")

    if discount_type == "percent" and discount_value > 100:
        raise ValueError("Diskon persen tidak boleh lebih dari 100")

    if max_uses is not None and max_uses <= 0:
        raise ValueError("Maksimal penggunaan harus lebih dari 0")

    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO coupons (code, description, discount_type, discount_value, max_uses, valid_from, valid_until, used_count)
                VALUES ($1, $2, $3, $4, $5, $6, $7, 0)
                RETURNING id;
                """,
                code.strip().upper(),
                description,
                discount_type,
                discount_value,
                max_uses,
                valid_from,
                valid_until,
            )
            voucher_id = row["id"]
            logger.info(
                "[voucher] Added voucher id=%s code=%s type=%s value=%s",
                voucher_id,
                code,
                discount_type,
                discount_value,
            )
            return voucher_id
        except Exception as e:
            error_msg = str(e)
            if "duplicate key" in error_msg.lower():
                raise ValueError(f"Voucher dengan kode '{code}' sudah ada") from e
            raise


async def edit_voucher(voucher_id: int, **fields) -> None:
    """
    Edit voucher di database.

    Args:
        voucher_id: ID voucher yang akan diedit
        **fields: Field yang akan diupdate

    Raises:
        ValueError: Jika validasi gagal
    """
    if not fields:
        raise ValueError("Tidak ada field yang akan diupdate")

    # Validasi data input
    if "discount_type" in fields and fields["discount_type"] not in ("percent", "flat"):
        raise ValueError("Tipe diskon harus 'percent' atau 'flat'")

    if "discount_value" in fields and fields["discount_value"] <= 0:
        raise ValueError("Nilai diskon harus lebih dari 0")

    discount_type = fields.get("discount_type")
    discount_value = fields.get("discount_value")
    if discount_type == "percent" and discount_value and discount_value > 100:
        raise ValueError("Diskon persen tidak boleh lebih dari 100")

    if (
        "max_uses" in fields
        and fields["max_uses"] is not None
        and fields["max_uses"] <= 0
    ):
        raise ValueError("Maksimal penggunaan harus lebih dari 0")

    if "code" in fields:
        if not fields["code"] or not fields["code"].strip():
            raise ValueError("Kode voucher tidak boleh kosong")
        fields["code"] = fields["code"].strip().upper()

    if "used_count" in fields:
        raise ValueError(
            "used_count tidak boleh diubah secara manual, gunakan increment_voucher_usage()"
        )

    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            sets = ", ".join([f"{k} = ${i + 2}" for i, k in enumerate(fields.keys())])
            values = [voucher_id] + list(fields.values())
            result = await conn.execute(
                f"UPDATE coupons SET {sets}, updated_at = NOW() WHERE id = $1;",
                *values,
            )

            if result == "UPDATE 0":
                raise ValueError(f"Voucher dengan ID {voucher_id} tidak ditemukan")

            logger.info(
                "[voucher] Updated voucher id=%s fields=%s",
                voucher_id,
                list(fields.keys()),
            )
        except ValueError:
            raise
        except Exception as e:
            error_msg = str(e)
            if "duplicate key" in error_msg.lower():
                raise ValueError(
                    f"Voucher dengan kode '{fields.get('code')}' sudah ada"
                ) from e
            raise


async def delete_voucher(voucher_id: int) -> None:
    """
    Hapus voucher dari database.

    Args:
        voucher_id: ID voucher yang akan dihapus

    Raises:
        ValueError: Jika voucher tidak ditemukan atau sudah digunakan
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Check if voucher has been used
        voucher = await conn.fetchrow(
            "SELECT used_count FROM coupons WHERE id = $1",
            voucher_id,
        )

        if not voucher:
            raise ValueError(f"Voucher dengan ID {voucher_id} tidak ditemukan")

        if voucher["used_count"] > 0:
            raise ValueError(
                f"Voucher tidak dapat dihapus karena sudah digunakan {voucher['used_count']} kali. "
                "Sebaiknya set valid_until ke masa lalu untuk menonaktifkan."
            )

        result = await conn.execute("DELETE FROM coupons WHERE id = $1;", voucher_id)

        if result == "DELETE 0":
            raise ValueError(f"Voucher dengan ID {voucher_id} tidak ditemukan")

        logger.info("[voucher] Deleted voucher id=%s", voucher_id)


async def list_vouchers(
    limit: int = 50, include_expired: bool = False
) -> List[Dict[str, Any]]:
    """
    List voucher dengan filter.

    Args:
        limit: Maksimal jumlah voucher yang dikembalikan
        include_expired: Apakah include voucher yang sudah expired

    Returns:
        List voucher
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        if include_expired:
            query = """
                SELECT * FROM coupons
                ORDER BY updated_at DESC
                LIMIT $1;
            """
        else:
            query = """
                SELECT * FROM coupons
                WHERE (valid_until IS NULL OR valid_until > NOW())
                ORDER BY updated_at DESC
                LIMIT $1;
            """

        rows = await conn.fetch(query, limit)
    return [dict(row) for row in rows]


async def get_voucher(code: str) -> Optional[Dict[str, Any]]:
    """
    Ambil voucher berdasarkan kode.

    Args:
        code: Kode voucher

    Returns:
        Dict voucher atau None jika tidak ditemukan
    """
    if not code or not code.strip():
        return None

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM coupons
            WHERE code = $1
            LIMIT 1;
            """,
            code.strip().upper(),
        )
    return dict(row) if row else None


async def get_voucher_by_id(voucher_id: int) -> Optional[Dict[str, Any]]:
    """
    Ambil voucher berdasarkan ID.

    Args:
        voucher_id: ID voucher

    Returns:
        Dict voucher atau None jika tidak ditemukan
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM coupons
            WHERE id = $1
            LIMIT 1;
            """,
            voucher_id,
        )
    return dict(row) if row else None


async def validate_voucher(code: str) -> Dict[str, Any]:
    """
    Validasi voucher untuk digunakan.

    Args:
        code: Kode voucher

    Returns:
        Dict dengan status validasi dan voucher data

    Example:
        {
            "valid": True,
            "voucher": {...},
            "error": None
        }
    """
    voucher = await get_voucher(code)

    if not voucher:
        return {
            "valid": False,
            "voucher": None,
            "error": "Voucher tidak ditemukan",
        }

    now = datetime.now(timezone.utc)

    # Check valid_from
    if voucher["valid_from"] and voucher["valid_from"] > now:
        return {
            "valid": False,
            "voucher": voucher,
            "error": f"Voucher belum aktif, mulai berlaku pada {voucher['valid_from']}",
        }

    # Check valid_until
    if voucher["valid_until"] and voucher["valid_until"] < now:
        return {
            "valid": False,
            "voucher": voucher,
            "error": "Voucher sudah kadaluarsa",
        }

    # Check max_uses
    if voucher["max_uses"] is not None:
        if voucher["used_count"] >= voucher["max_uses"]:
            return {
                "valid": False,
                "voucher": voucher,
                "error": f"Voucher sudah mencapai batas penggunaan ({voucher['max_uses']} kali)",
            }

    return {
        "valid": True,
        "voucher": voucher,
        "error": None,
    }


async def increment_voucher_usage(voucher_id: int) -> None:
    """
    Increment used_count untuk voucher setelah digunakan.

    Args:
        voucher_id: ID voucher

    Raises:
        ValueError: Jika voucher tidak ditemukan atau sudah mencapai max_uses
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Lock row untuk update
            voucher = await conn.fetchrow(
                """
                SELECT id, code, used_count, max_uses
                FROM coupons
                WHERE id = $1
                FOR UPDATE;
                """,
                voucher_id,
            )

            if not voucher:
                raise ValueError(f"Voucher dengan ID {voucher_id} tidak ditemukan")

            # Check max_uses
            if voucher["max_uses"] is not None:
                if voucher["used_count"] >= voucher["max_uses"]:
                    raise ValueError(
                        f"Voucher '{voucher['code']}' sudah mencapai batas penggunaan "
                        f"({voucher['max_uses']} kali)"
                    )

            # Increment used_count
            await conn.execute(
                """
                UPDATE coupons
                SET used_count = used_count + 1,
                    updated_at = NOW()
                WHERE id = $1;
                """,
                voucher_id,
            )

            logger.info(
                "[voucher] Incremented usage for voucher id=%s code=%s (now %s uses)",
                voucher_id,
                voucher["code"],
                voucher["used_count"] + 1,
            )


async def increment_voucher_usage_by_code(code: str) -> None:
    """
    Increment used_count untuk voucher berdasarkan kode.

    Args:
        code: Kode voucher

    Raises:
        ValueError: Jika voucher tidak ditemukan atau sudah mencapai max_uses
    """
    voucher = await get_voucher(code)
    if not voucher:
        raise ValueError(f"Voucher dengan kode '{code}' tidak ditemukan")

    await increment_voucher_usage(voucher["id"])


async def calculate_discount(voucher: Dict[str, Any], total_cents: int) -> int:
    """
    Hitung nilai diskon dari voucher.

    Args:
        voucher: Dict data voucher
        total_cents: Total harga dalam cents

    Returns:
        Nilai diskon dalam cents
    """
    if voucher["discount_type"] == "percent":
        discount_cents = int(total_cents * voucher["discount_value"] / 100)
    else:  # flat
        discount_cents = voucher["discount_value"]

    # Pastikan diskon tidak melebihi total
    return min(discount_cents, total_cents)


async def get_voucher_usage_stats() -> List[Dict[str, Any]]:
    """
    Ambil statistik penggunaan voucher.

    Returns:
        List voucher dengan usage statistics
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                id,
                code,
                description,
                discount_type,
                discount_value,
                max_uses,
                used_count,
                valid_from,
                valid_until,
                CASE
                    WHEN max_uses IS NULL THEN NULL
                    ELSE ROUND((used_count::NUMERIC / max_uses::NUMERIC) * 100, 2)
                END as usage_percentage,
                CASE
                    WHEN valid_until IS NOT NULL AND valid_until < NOW() THEN TRUE
                    ELSE FALSE
                END as is_expired
            FROM coupons
            ORDER BY used_count DESC, updated_at DESC;
            """
        )
    return [dict(row) for row in rows]
