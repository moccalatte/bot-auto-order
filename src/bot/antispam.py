"""Anti-spam guard to throttle abusive users."""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass
from time import monotonic
from typing import Deque, Dict


@dataclass(slots=True)
class AntiSpamDecision:
    """Decision returned by anti-spam guard."""

    allowed: bool = True
    warn_user: bool = False
    notify_admin: bool = False


class AntiSpamGuard:
    """Track per-user activity bursts and block abusive spam."""

    def __init__(
        self,
        *,
        min_interval_seconds: float = 1.0,
        burst_window_seconds: float = 5.0,
        max_actions_in_burst: int = 5,
        notify_interval_seconds: float = 120.0,
    ) -> None:
        self._min_interval = min_interval_seconds
        self._burst_window = burst_window_seconds
        self._max_actions = max_actions_in_burst
        self._notify_interval = notify_interval_seconds

        self._actions: Dict[int, Deque[float]] = defaultdict(deque)
        self._last_notification: Dict[int, float] = {}
        self._lock = asyncio.Lock()

    async def register_action(self, user_id: int) -> AntiSpamDecision:
        """Record user action and decide whether to allow further handling."""

        now = monotonic()
        decision = AntiSpamDecision()

        async with self._lock:
            entries = self._actions[user_id]

            # Drop entries older than burst window
            while entries and now - entries[0] > self._burst_window:
                entries.popleft()

            if entries and now - entries[-1] <= self._min_interval:
                entries.append(now)
            else:
                entries.clear()
                entries.append(now)

            if len(entries) >= self._max_actions:
                decision.allowed = False
                last_notified = self._last_notification.get(user_id, 0.0)
                if now - last_notified >= self._notify_interval:
                    decision.warn_user = True
                    decision.notify_admin = True
                    self._last_notification[user_id] = now
            else:
                decision.allowed = True

        return decision

    async def reset_user(self, user_id: int) -> None:
        """Clear stored activity for a user."""
        async with self._lock:
            self._actions.pop(user_id, None)
            self._last_notification.pop(user_id, None)
