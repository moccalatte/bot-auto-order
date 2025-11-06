"""Registrasi job terjadwal untuk health-check dan backup otomatis."""

from __future__ import annotations

from datetime import time
from typing import Optional
from zoneinfo import ZoneInfo

from telegram.ext import Application

from src.core.config import get_settings
from src.core.tasks import backup_job, healthcheck_job, check_expired_payments_job
from src.core.telemetry import telemetry_flush_job


def _parse_time(value: str, timezone: str) -> time:
    hour, minute = 0, 0
    try:
        parts = value.split(":", maxsplit=1)
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
    except Exception:  # pragma: no cover - fallback
        hour, minute = 0, 0
    return time(hour=hour % 24, minute=minute % 60, tzinfo=ZoneInfo(timezone))


def register_scheduled_jobs(application: Application) -> None:
    """Daftarkan job periodik berdasarkan konfigurasi env."""

    settings = get_settings()
    job_queue = application.job_queue
    if job_queue is None:  # pragma: no cover - defensive
        return

    if settings.enable_auto_healthcheck:
        interval = max(1, settings.healthcheck_interval_minutes) * 60
        job_queue.run_repeating(
            healthcheck_job,
            interval=interval,
            first=20,
            name="auto_healthcheck",
        )

    if settings.enable_auto_backup:
        backup_time = _parse_time(settings.backup_time, settings.bot_timezone)
        job_queue.run_daily(
            backup_job,
            time=backup_time,
            name="auto_backup",
        )

    # Monitor expired payments every minute
    job_queue.run_repeating(
        check_expired_payments_job,
        interval=60,  # Check every 60 seconds
        first=10,  # Start after 10 seconds
        name="check_expired_payments",
    )

    # Flush telemetry to database every 6 hours
    telemetry_tracker = application.bot_data.get("telemetry")
    if telemetry_tracker:
        job_queue.run_repeating(
            lambda context: telemetry_flush_job(telemetry_tracker),
            interval=21600,  # 6 hours in seconds
            first=300,  # Start after 5 minutes
            name="telemetry_flush",
        )
