"""Lightweight telemetry tracker."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TelemetrySnapshot:
    """Snapshot of bot metrics."""

    total_users: int = 0
    successful_transactions: int = 0
    failed_transactions: int = 0
    carts_created: int = 0
    carts_abandoned: int = 0


@dataclass(slots=True)
class TelemetryTracker:
    """Thread-safe metrics collector with periodic logging."""

    interval_seconds: int = 300
    snapshot: TelemetrySnapshot = field(default_factory=TelemetrySnapshot)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _task: asyncio.Task | None = None

    async def start(self) -> None:
        """Spawn background task if not already running."""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run())
            logger.info("📈 TelemetryTracker started.")

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self.interval_seconds)
            await self.flush()

    async def flush(self) -> None:
        """Write current metrics to log."""
        async with self._lock:
            metrics = vars(self.snapshot).copy()
            logger.info("📊 Telemetry: %s", metrics)

    async def flush_to_db(self) -> None:
        """Write current metrics to database telemetry_daily table."""
        from src.services.postgres import get_pool

        async with self._lock:
            metrics = vars(self.snapshot).copy()

        try:
            pool = await get_pool()
            today = datetime.now(timezone.utc).date()

            async with pool.acquire() as conn:
                # Upsert daily telemetry
                await conn.execute(
                    """
                    INSERT INTO telemetry_daily (
                        date,
                        total_users,
                        total_transactions,
                        total_revenue_cents,
                        created_at
                    )
                    VALUES ($1, $2, $3, $4, NOW())
                    ON CONFLICT (date)
                    DO UPDATE SET
                        total_users = EXCLUDED.total_users,
                        total_transactions = EXCLUDED.total_transactions,
                        total_revenue_cents = EXCLUDED.total_revenue_cents,
                        created_at = NOW();
                    """,
                    today,
                    metrics.get("total_users", 0),
                    metrics.get("successful_transactions", 0),
                    0,  # Revenue tracking can be added later
                )
                logger.info("📊 Telemetry flushed to DB for date: %s", today)
        except Exception as exc:
            logger.warning("[telemetry] Failed to flush to DB: %s", exc)

    async def increment(self, field_name: str, amount: int = 1) -> None:
        """Increase metric by given amount."""
        async with self._lock:
            if not hasattr(self.snapshot, field_name):
                raise AttributeError(f"Unknown metric field: {field_name}")
            current_value = getattr(self.snapshot, field_name)
            setattr(self.snapshot, field_name, current_value + amount)

    async def update_from_dict(self, data: Dict[str, int]) -> None:
        """Replace metric values with those provided in mapping."""
        async with self._lock:
            for key, value in data.items():
                if hasattr(self.snapshot, key):
                    setattr(self.snapshot, key, value)
                else:
                    logger.warning("Ignoring unknown telemetry key: %s", key)


async def telemetry_flush_job(tracker: TelemetryTracker) -> None:
    """
    Background job to periodically flush telemetry to database.
    Should be scheduled to run daily or every few hours.
    """
    try:
        await tracker.flush_to_db()
    except Exception as exc:
        logger.exception("[telemetry_job] Failed to flush: %s", exc)
