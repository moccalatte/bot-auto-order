"""Helper untuk enkripsi/dekripsi data sensitif."""

from __future__ import annotations

import logging
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from src.core.config import get_settings


logger = logging.getLogger(__name__)


class EncryptionUnavailable(RuntimeError):
    """Dilempar saat kunci enkripsi tidak disediakan."""


@lru_cache(maxsize=1)
def _get_cipher() -> Fernet:
    settings = get_settings()
    key = settings.data_encryption_key
    if not key:
        raise EncryptionUnavailable(
            "DATA_ENCRYPTION_KEY belum di-set. Gunakan 'openssl rand -base64 32'."
        )
    try:
        return Fernet(key.encode())
    except Exception as exc:  # pragma: no cover - invalid key
        raise EncryptionUnavailable(f"Kunci enkripsi tidak valid: {exc}") from exc


def encrypt_text(value: str | None) -> str | None:
    """Enkripsi teks, mengembalikan base64 token."""

    if value is None:
        return None
    cipher = _get_cipher()
    token = cipher.encrypt(value.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_text(token: str | None) -> str | None:
    """Dekripsi teks terenkripsi."""

    if token is None:
        return None
    cipher = _get_cipher()
    try:
        value = cipher.decrypt(token.encode("utf-8"))
        return value.decode("utf-8")
    except InvalidToken:
        logger.error("Token enkripsi SNK tidak valid atau korup.")
        return None

