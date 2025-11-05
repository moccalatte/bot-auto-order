"""Fungsi job terjadwal untuk health-check dan backup."""

from __future__ import annotations

import asyncio
import logging
from argparse import Namespace

from telegram.ext import ContextTypes

from src.core.config import get_settings
from src.tools.healthcheck import run_healthcheck
from src.tools.backup_manager import create_backup


logger = logging.getLogger(__name__)


async def healthcheck_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Jalankan health-check periodik."""

    try:
        await run_healthcheck(configure_logging=False)
    except Exception as exc:  # pragma: no cover - observability
        logger.exception("Health-check job gagal: %s", exc)


async def backup_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Jalankan backup terenkripsi secara berkala."""

    settings = get_settings()
    offsite = settings.backup_automatic_offsite
    args = Namespace(offsite=offsite)
    try:
        await asyncio.to_thread(create_backup, args)
    except SystemExit:
        # create_backup bisa memanggil SystemExit jika env tidak lengkap.
        logger.warning("Backup job dilewati, BACKUP_ENCRYPTION_PASSWORD mungkin belum di-set.")
    except Exception as exc:  # pragma: no cover - observability
        logger.exception("Backup job gagal: %s", exc)
