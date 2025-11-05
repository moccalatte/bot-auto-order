"""Persistence helper untuk antrian broadcast admin."""

from __future__ import annotations

import logging
from typing import Iterable, List, Optional

from src.services.postgres import get_pool


logger = logging.getLogger(__name__)


async def _ensure_tables() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS broadcast_jobs (
                id BIGSERIAL PRIMARY KEY,
                actor_telegram_id BIGINT NOT NULL,
                message TEXT,
                media_file_id TEXT,
                media_type TEXT,
                status VARCHAR(16) DEFAULT 'pending',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                started_at TIMESTAMPTZ,
                completed_at TIMESTAMPTZ
            );
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS broadcast_job_targets (
                id BIGSERIAL PRIMARY KEY,
                job_id BIGINT NOT NULL REFERENCES broadcast_jobs(id) ON DELETE CASCADE,
                telegram_id BIGINT NOT NULL,
                status VARCHAR(16) DEFAULT 'pending',
                retries INTEGER DEFAULT 0,
                last_error TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                sent_at TIMESTAMPTZ,
                UNIQUE (job_id, telegram_id)
            );
            """
        )


async def create_job(
    *,
    actor_telegram_id: int,
    message: str | None,
    media_file_id: str | None,
    media_type: str | None,
    targets: Iterable[int],
) -> int:
    """Enqueue broadcast job dan targetnya."""

    await _ensure_tables()
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                INSERT INTO broadcast_jobs (actor_telegram_id, message, media_file_id, media_type)
                VALUES ($1, $2, $3, $4)
                RETURNING id;
                """,
                actor_telegram_id,
                message,
                media_file_id,
                media_type,
            )
            job_id = int(row["id"])
            telegram_ids = list(dict.fromkeys(int(t) for t in targets))
            if telegram_ids:
                await conn.executemany(
                    """
                    INSERT INTO broadcast_job_targets (job_id, telegram_id)
                    VALUES ($1, $2)
                    ON CONFLICT (job_id, telegram_id) DO NOTHING;
                    """,
                    [(job_id, tid) for tid in telegram_ids],
                )
            logger.info(
                "[broadcast_queue] Job %s dibuat oleh %s dengan %s target.",
                job_id,
                actor_telegram_id,
                len(telegram_ids),
            )
            return job_id


async def fetch_pending_targets(limit: int = 20) -> List[dict]:
    """Ambil target broadcast yang belum dikirim."""

    await _ensure_tables()
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            rows = await conn.fetch(
                """
                WITH candidate AS (
                    SELECT id, job_id
                    FROM broadcast_job_targets
                    WHERE status = 'pending'
                    ORDER BY created_at, id
                    LIMIT $1
                    FOR UPDATE SKIP LOCKED
                )
                UPDATE broadcast_job_targets tgt
                SET status = 'processing'
                FROM candidate
                WHERE tgt.id = candidate.id
                RETURNING
                    tgt.id,
                    tgt.job_id,
                    tgt.telegram_id,
                    (SELECT message FROM broadcast_jobs WHERE id = tgt.job_id) AS message,
                    (SELECT media_file_id FROM broadcast_jobs WHERE id = tgt.job_id) AS media_file_id,
                    (SELECT media_type FROM broadcast_jobs WHERE id = tgt.job_id) AS media_type;
                """,
                limit,
            )
            job_ids = {int(row["job_id"]) for row in rows}
            if job_ids:
                await conn.execute(
                    """
                    UPDATE broadcast_jobs
                    SET started_at = COALESCE(started_at, NOW()), status = 'running'
                    WHERE id = ANY($1::BIGINT[]);
                    """,
                    list(job_ids),
                )
    return [dict(row) for row in rows]


async def mark_target_success(target_id: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE broadcast_job_targets
            SET status = 'sent', sent_at = NOW(), last_error = NULL
            WHERE id = $1;
            """,
            target_id,
        )


async def mark_target_failed(target_id: int, error: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE broadcast_job_targets
            SET status = 'failed', retries = retries + 1, last_error = $2
            WHERE id = $1;
            """,
            target_id,
            error[:512],
        )


async def finalize_jobs() -> None:
    """Tandai job selesai jika semua target terkirim atau gagal permanen."""

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT job.id
            FROM broadcast_jobs job
            WHERE job.status IN ('pending', 'running')
            AND NOT EXISTS (
                SELECT 1 FROM broadcast_job_targets tgt
                WHERE tgt.job_id = job.id AND tgt.status = 'pending'
            );
            """
        )
        for row in rows:
            job_id = int(row["id"])
            await conn.execute(
                """
                UPDATE broadcast_jobs
                SET status = 'completed', completed_at = NOW()
                WHERE id = $1;
                """,
                job_id,
            )
            logger.info("[broadcast_queue] Job %s selesai.", job_id)


async def get_job_summary(job_id: int) -> dict:
    await _ensure_tables()
    pool = await get_pool()
    async with pool.acquire() as conn:
        job = await conn.fetchrow(
            """
            SELECT id, status, created_at, started_at, completed_at
            FROM broadcast_jobs WHERE id = $1;
            """,
            job_id,
        )
        counts = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE status = 'pending') AS pending,
                COUNT(*) FILTER (WHERE status = 'sent') AS sent,
                COUNT(*) FILTER (WHERE status = 'failed') AS failed
            FROM broadcast_job_targets
            WHERE job_id = $1;
            """,
            job_id,
        )
    return {
        "job": dict(job) if job else {},
        "counts": dict(counts) if counts else {},
    }
