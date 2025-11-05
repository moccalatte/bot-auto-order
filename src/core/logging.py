"""Logging utilities that follow project_rules.md requirements."""

from __future__ import annotations

import asyncio
import logging
import logging.config
import time
from datetime import datetime
from pathlib import Path
from collections import deque

from .config import get_settings
from src.services.owner_alerts import notify_owners


class OwnerAlertHandler(logging.Handler):
    """Kirim log level tinggi ke owner via Telegram."""

    def __init__(self, level: int = logging.ERROR, ttl_seconds: int = 60) -> None:
        super().__init__(level)
        self._recent: deque[tuple[str, float]] = deque(maxlen=50)
        self._ttl = ttl_seconds

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover - async side effects
        if record.levelno < self.level:
            return
        message = self.format(record)
        now = time.time()
        key = f"{record.name}:{record.getMessage()}"
        # Deduplicate dalam window TTL
        self._recent = deque(
            [(k, ts) for k, ts in self._recent if now - ts < self._ttl],
            maxlen=self._recent.maxlen,
        )
        if any(k == key for k, _ in self._recent):
            return
        self._recent.append((key, now))

        async def _send() -> None:
            await notify_owners(f"🚨 Log {record.levelname}: {message}")

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_send())
        except RuntimeError:
            asyncio.run(_send())


def _build_log_path(service_name: str) -> Path:
    date_suffix = datetime.now().strftime("%Y-%m-%d")
    base_dir = Path("logs") / service_name
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / f"{date_suffix}.log"


def setup_logging(service_name: str = "telegram-bot") -> None:
    """Configure logging with file + console handler."""

    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    log_path = _build_log_path(service_name)

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "[%(asctime)s] [%(levelname)s] %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "standard",
                "level": level,
            },
            "file": {
                "class": "logging.FileHandler",
                "formatter": "standard",
                "level": level,
                "filename": log_path,
                "encoding": "utf-8",
            },
        },
        "root": {
            "handlers": ["console", "file"],
            "level": level,
        },
    }

    logging.config.dictConfig(logging_config)

    if settings.enable_owner_alerts:
        threshold = getattr(
            logging, settings.owner_alert_threshold.upper(), logging.ERROR
        )
        handler = OwnerAlertHandler(level=threshold)
        handler.setFormatter(
            logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
        )
        logging.getLogger().addHandler(handler)
