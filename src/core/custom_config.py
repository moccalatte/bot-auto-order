# custom_config.py
"""
Modul penyimpanan & validasi konfigurasi kustom admin untuk Bot Auto Order.
Semua perubahan konfigurasi disimpan di database, bukan hardcode.
Mendukung backup, restore, validasi placeholder, dan audit log.
"""

from typing import Dict, Any, Optional, List
import asyncio
import re
import logging

logger = logging.getLogger(__name__)

# Placeholder yang diizinkan dalam template pesan
ALLOWED_PLACEHOLDERS = {
    "nama",
    "order_id",
    "produk",
    "jumlah",
    "harga",
    "tanggal",
    "status",
    "store_name",
    "total_users",
    "total_transactions",
    "telegram_id",
    "saldo",
    "bank_id",
    "verified",
}


class ConfigValidationError(Exception):
    """Error validasi konfigurasi kustom admin."""

    pass


class CustomConfigManager:
    """
    Manajer konfigurasi kustom admin.
    Semua konfigurasi disimpan di database melalui adapter (inject di init).
    """

    def __init__(self, db_adapter):
        """
        Args:
            db_adapter: objek adapter database dengan API CRUD sederhana.
        """
        self.db = db_adapter

    def validate_placeholders(self, template: str) -> None:
        """
        Validasi placeholder dalam template pesan.
        Args:
            template (str): template pesan yang akan divalidasi.
        Raises:
            ConfigValidationError: jika ditemukan placeholder tidak valid.
        """
        found = set(re.findall(r"\{(\w+)\}", template))
        invalid = found - ALLOWED_PLACEHOLDERS
        if invalid:
            raise ConfigValidationError(
                f"Placeholder tidak valid: {', '.join(invalid)}. "
                f"Yang diizinkan: {', '.join(sorted(ALLOWED_PLACEHOLDERS))}"
            )

    async def get_config(self, key: str) -> Optional[str]:
        """
        Ambil konfigurasi kustom berdasarkan key.
        Args:
            key (str): nama konfigurasi.
        Returns:
            Optional[str]: nilai konfigurasi, None jika tidak ada.
        """
        return await self.db.get_config(key)

    async def set_config(
        self, key: str, value: str, *, actor_id: Optional[int] = None
    ) -> None:
        """
        Simpan konfigurasi kustom dengan validasi.
        Args:
            key (str): nama konfigurasi.
            value (str): nilai konfigurasi.
        Raises:
            ConfigValidationError: jika validasi gagal.
        """
        self.validate_placeholders(value)
        await self.db.set_config(key, value, updated_by=actor_id)
        logger.info(
            "[custom_config] Konfigurasi '%s' diubah oleh admin %s.",
            key,
            actor_id or "unknown",
        )

    async def backup(self) -> Dict[str, Any]:
        """
        Backup seluruh konfigurasi kustom.
        Returns:
            Dict[str, Any]: dict semua konfigurasi.
        """
        return await self.db.backup_configs()

    async def restore(
        self, configs: Dict[str, Any], *, actor_id: Optional[int] = None
    ) -> None:
        """
        Restore konfigurasi dari backup.
        Args:
            configs (Dict[str, Any]): dict konfigurasi hasil backup.
        """
        for key, value in configs.items():
            self.validate_placeholders(str(value))
            await self.db.set_config(key, str(value), updated_by=actor_id)
        logger.info(
            "[custom_config] Restore konfigurasi berhasil oleh admin %s.",
            actor_id or "unknown",
        )

    async def audit_log(self) -> List[Dict[str, Any]]:
        """
        Ambil log audit perubahan konfigurasi.
        Returns:
            List[Dict[str, Any]]: list log audit.
        """
        return await self.db.get_audit_logs()


# Adapter database minimal (contoh, implementasi asli di modul lain)
class DummyDBAdapter:
    def __init__(self):
        self._store = {}
        self._audit = []

    async def get_config(self, key):
        return self._store.get(key)

    async def set_config(self, key, value, *, updated_by=None):
        self._store[key] = value
        self._audit.append(
            {
                "key": key,
                "value": value,
                "action": "set",
                "updated_by": updated_by,
            }
        )

    async def backup_configs(self):
        return dict(self._store)

    async def get_audit_logs(self):
        return list(self._audit)


class PostgresConfigAdapter:
    """
    Adapter konfigurasi kustom berbasis Postgres.
    Menyimpan data di tabel admin_custom_configs dan log audit di admin_custom_config_audit.
    """

    def __init__(self) -> None:
        self._initialised = False
        self._lock = asyncio.Lock()

    async def _ensure_tables(self) -> None:
        """Pastikan tabel penyimpanan konfigurasi tersedia."""
        if self._initialised:
            return
        async with self._lock:
            if self._initialised:
                return
            from src.services.postgres import get_pool

            pool = await get_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS admin_custom_configs (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_by BIGINT,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        updated_at TIMESTAMPTZ DEFAULT NOW()
                    );
                    """
                )
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS admin_custom_config_audit (
                        id BIGSERIAL PRIMARY KEY,
                        key TEXT NOT NULL,
                        value TEXT NOT NULL,
                        action TEXT NOT NULL,
                        updated_by BIGINT,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    );
                    """
                )
            self._initialised = True

    async def get_config(self, key: str) -> Optional[str]:
        await self._ensure_tables()
        from src.services.postgres import get_pool

        pool = await get_pool()
        row = await pool.fetchrow(
            """
            SELECT value
            FROM admin_custom_configs
            WHERE key = $1;
            """,
            key,
        )
        return row["value"] if row else None

    async def set_config(
        self, key: str, value: str, *, updated_by: Optional[int] = None
    ) -> None:
        await self._ensure_tables()
        from src.services.postgres import get_pool

        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO admin_custom_configs (key, value, updated_by, updated_at)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT (key)
                DO UPDATE SET
                    value = EXCLUDED.value,
                    updated_by = EXCLUDED.updated_by,
                    updated_at = NOW();
                """,
                key,
                value,
                updated_by,
            )
            await conn.execute(
                """
                INSERT INTO admin_custom_config_audit (key, value, action, updated_by)
                VALUES ($1, $2, 'set', $3);
                """,
                key,
                value,
                updated_by,
            )

    async def backup_configs(self) -> Dict[str, Any]:
        await self._ensure_tables()
        from src.services.postgres import get_pool

        pool = await get_pool()
        rows = await pool.fetch(
            """
            SELECT key, value
            FROM admin_custom_configs;
            """
        )
        return {row["key"]: row["value"] for row in rows}

    async def get_audit_logs(self) -> List[Dict[str, Any]]:
        await self._ensure_tables()
        from src.services.postgres import get_pool

        pool = await get_pool()
        rows = await pool.fetch(
            """
            SELECT key, value, action, updated_by, created_at
            FROM admin_custom_config_audit
            ORDER BY id DESC
            LIMIT 100;
            """
        )
        return [dict(row) for row in rows]
