"""Statistics helpers."""

from __future__ import annotations

from src.services.postgres import get_pool


async def get_bot_statistics() -> dict[str, int]:
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT
            (SELECT COUNT(*) FROM users) AS total_users,
            (SELECT COUNT(*) FROM orders WHERE status = 'paid') AS total_transactions;
        """
    )
    if row is None:
        return {"total_users": 0, "total_transactions": 0}
    return {
        "total_users": int(row["total_users"]),
        "total_transactions": int(row["total_transactions"]),
    }
