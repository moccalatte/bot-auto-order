"""Health-check CLI for monitoring bot availability."""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import httpx
import psutil
import shutil
import uvloop

from src.core.config import get_settings
from src.core.logging import setup_logging
from src.services.owner_alerts import notify_owners
from src.services.postgres import get_pool


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


async def check_telegram_api(client: httpx.AsyncClient, token: str) -> CheckResult:
    """Verify Telegram Bot API availability."""
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        response = await client.get(url)
        data = response.json()
        ok = response.status_code == 200 and data.get("ok") is True
        detail = "API reachable" if ok else f"API error: {data}"
        return CheckResult("telegram_api", ok, detail)
    except Exception as exc:  # pragma: no cover - network errors
        return CheckResult("telegram_api", False, f"Exception: {exc}")


async def check_database() -> CheckResult:
    """Verify Postgres connectivity."""
    try:
        pool = await get_pool()
        async with pool.acquire() as connection:
            value = await connection.fetchval("SELECT 1;")
        ok = int(value or 0) == 1
        detail = "Database reachable" if ok else f"Unexpected result: {value}"
        return CheckResult("database", ok, detail)
    except Exception as exc:
        return CheckResult("database", False, f"Exception: {exc}")


def check_disk_usage(path: Path, threshold_percent: float) -> CheckResult:
    """Check disk utilisation for the given path."""
    total, used, free = shutil.disk_usage(path)
    usage = (used / total) * 100 if total else 0
    ok = usage < threshold_percent
    detail = f"Usage {usage:.1f}% (threshold {threshold_percent:.1f}%)"
    return CheckResult(f"disk:{path}", ok, detail)


def check_cpu(threshold_percent: float) -> CheckResult:
    usage = psutil.cpu_percent(interval=1)
    ok = usage < threshold_percent
    detail = f"CPU {usage:.1f}% (threshold {threshold_percent:.1f}%)"
    return CheckResult("cpu", ok, detail)


def check_memory(threshold_percent: float) -> CheckResult:
    mem = psutil.virtual_memory()
    usage = mem.percent
    ok = usage < threshold_percent
    detail = f"RAM {usage:.1f}% (threshold {threshold_percent:.1f}%)"
    return CheckResult("memory", ok, detail)


def check_log_usage(path: Path, threshold_mb: int) -> CheckResult:
    total_bytes = 0
    for file in path.rglob("*"):
        if file.is_file():
            total_bytes += file.stat().st_size
    usage_mb = total_bytes / (1024 * 1024)
    ok = usage_mb <= threshold_mb
    detail = f"Log usage {usage_mb:.1f} MB (threshold {threshold_mb} MB)"
    return CheckResult("log_usage", ok, detail)


async def emit_owner_alert(
    failures: List[CheckResult],
    *,
    client: httpx.AsyncClient,
) -> None:
    """Send aggregated alert message to owner accounts."""
    if not failures:
        return
    settings = get_settings()
    timestamp = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    lines = [
        f"🚨 Health-check gagal untuk {settings.store_name}",
        f"🕒 {timestamp}",
        "",
    ]
    lines.extend(f"- {item.name}: {item.detail}" for item in failures)
    await notify_owners("\n".join(lines), client=client)


async def run_healthcheck(
    *,
    configure_logging: bool = False,
    cleanup_pool: bool = False,
) -> List[CheckResult]:
    """Jalankan health-check dan kembalikan daftar hasil."""

    if configure_logging:
        setup_logging(service_name="health-check")
    settings = get_settings()

    results: List[CheckResult] = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        results.append(await check_telegram_api(client, settings.telegram_bot_token))
        results.append(await check_database())

        logs_path = Path(os.environ.get("BOT_LOG_PATH", "logs"))
        results.append(
            check_disk_usage(logs_path, settings.health_disk_threshold)
        )
        results.append(check_cpu(settings.health_cpu_threshold))
        results.append(check_memory(settings.health_memory_threshold))
        results.append(check_log_usage(logs_path, settings.log_usage_threshold_mb))

        failures = [item for item in results if not item.ok]

        for item in results:
            log_func = logger.info if item.ok else logger.error
            log_func("[health] %s - %s", item.name, item.detail)

        await emit_owner_alert(failures, client=client)

    # Close pool after checks to release connections.
    if cleanup_pool:
        try:
            pool = await get_pool()
            await pool.close()
        except Exception:  # pragma: no cover - defensive
            logger.debug("Pool already closed after health-check.")

    status_text = "semua OK ✅" if not failures else "ADA MASALAH ⚠️"
    logger.info("Health-check selesai, status: %s", status_text)
    return results


async def main() -> None:
    """Entry point untuk CLI."""
    await run_healthcheck(configure_logging=True, cleanup_pool=True)


if __name__ == "__main__":
    uvloop.install()
    asyncio.run(main())
