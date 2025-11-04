bot - auto - order / src / core / custom_config.py
# custom_config.py
"""
Modul penyimpanan & validasi konfigurasi kustom admin untuk Bot Auto Order.
Semua perubahan konfigurasi disimpan di database, bukan hardcode.
Mendukung backup, restore, validasi placeholder, dan audit log.
"""

from typing import Dict, Any, Optional, List
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

    async def set_config(self, key: str, value: str) -> None:
        """
        Simpan konfigurasi kustom dengan validasi.
        Args:
            key (str): nama konfigurasi.
            value (str): nilai konfigurasi.
        Raises:
            ConfigValidationError: jika validasi gagal.
        """
        self.validate_placeholders(value)
        await self.db.set_config(key, value)
        logger.info(f"[custom_config] Konfigurasi '{key}' diubah oleh admin.")

    async def backup(self) -> Dict[str, Any]:
        """
        Backup seluruh konfigurasi kustom.
        Returns:
            Dict[str, Any]: dict semua konfigurasi.
        """
        return await self.db.backup_configs()

    async def restore(self, configs: Dict[str, Any]) -> None:
        """
        Restore konfigurasi dari backup.
        Args:
            configs (Dict[str, Any]): dict konfigurasi hasil backup.
        """
        for key, value in configs.items():
            self.validate_placeholders(str(value))
            await self.db.set_config(key, str(value))
        logger.info("[custom_config] Restore konfigurasi berhasil.")

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

    async def set_config(self, key, value):
        self._store[key] = value
        self._audit.append(
            {
                "key": key,
                "value": value,
                "action": "set",
            }
        )

    async def backup_configs(self):
        return dict(self._store)

    async def get_audit_logs(self):
        return list(self._audit)


# Contoh penggunaan:
# db_adapter = DummyDBAdapter()
# config_mgr = CustomConfigManager(db_adapter)
# await config_mgr.set_config("order_message", "Halo {nama}, pesanan {order_id} diterima!")
