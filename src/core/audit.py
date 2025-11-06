"""Lightweight audit logging utilities."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

AUDIT_DIR = Path("logs/audit")
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)


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
    audit_logger = _get_audit_logger()
    audit_logger.info(json.dumps(entry, ensure_ascii=False))


async def audit_log_db(
    *, actor_id: int | str | None, action: str, details: Dict[str, Any]
) -> None:
    """
    Write audit entry to database audit_log table.

    Args:
        actor_id: Telegram/admin identifier if available.
        action: Short action descriptor (e.g., 'product_created', 'order_cancelled').
        details: Additional structured payload (stored as JSONB).
    """
    from src.services.postgres import get_pool

    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO audit_log (timestamp, actor_id, action, details, entity_type, entity_id)
                VALUES (NOW(), $1, $2, $3, $4, $5);
                """,
                str(actor_id) if actor_id else None,
                action,
                json.dumps(details, ensure_ascii=False),
                details.get("entity_type"),
                details.get("entity_id"),
            )
    except Exception as exc:
        logger.warning("[audit_log_db] Failed to write audit log: %s", exc)


async def audit_log_full(
    *, actor_id: int | str | None, action: str, details: Dict[str, Any]
) -> None:
    """
    Write audit entry to both file and database.

    Args:
        actor_id: Telegram/admin identifier if available.
        action: Short action descriptor.
        details: Additional structured payload.
    """
    # Write to file
    audit_log(actor_id=actor_id, action=action, details=details)

    # Write to database (async)
    try:
        await audit_log_db(actor_id=actor_id, action=action, details=details)
    except Exception as exc:
        logger.warning("[audit_log_full] DB write failed: %s", exc)
