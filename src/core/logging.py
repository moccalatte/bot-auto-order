"""Logging utilities that follow project_rules.md requirements."""

from __future__ import annotations

import logging
import logging.config
from datetime import datetime
from pathlib import Path

from .config import get_settings


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
