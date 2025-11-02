"""Lightweight telemetry tracker."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
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
            metrics = self.snapshot.__dict__.copy()
            logger.info("📊 Telemetry: %s", metrics)

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
