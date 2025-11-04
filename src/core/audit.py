"""Lightweight audit logging utilities."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

AUDIT_DIR = Path("logs/audit")
AUDIT_DIR.mkdir(parents=True, exist_ok=True)


def _get_audit_logger() -> logging.Logger:
    """Return audit logger writing to daily log file."""
    logger = logging.getLogger("audit")
    current_path = _current_log_path()
    if logger.handlers:
        handler = logger.handlers[0]
        if getattr(handler, "baseFilename", None) != current_path:
            logger.removeHandler(handler)
            handler.close()
        else:
            return logger

    if not logger.handlers:
        logger.setLevel(logging.INFO)
        logger.propagate = False
        handler = logging.FileHandler(current_path, encoding="utf-8")
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def _current_log_path() -> str:
    now = datetime.now(timezone.utc)
    return str(AUDIT_DIR / f"{now.strftime('%Y-%m-%d')}.log")


def audit_log(
    *, actor_id: int | str | None, action: str, details: Dict[str, Any]
) -> None:
    """
    Append audit entry as JSON line.

    Args:
        actor_id: Telegram/admin identifier if available.
        action: Short action descriptor.
        details: Additional structured payload.
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor_id": actor_id,
        "action": action,
        "details": details,
    }
    logger = _get_audit_logger()
    logger.info(json.dumps(entry, ensure_ascii=False))
