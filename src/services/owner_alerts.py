"""Utilities for notifying owner accounts via Telegram."""

from __future__ import annotations

import logging
from typing import Sequence

import httpx

from src.core.config import get_settings


logger = logging.getLogger(__name__)


async def notify_owners(
    message: str,
    *,
    parse_mode: str | None = None,
    disable_notification: bool = False,
    client: httpx.AsyncClient | None = None,
) -> None:
    """Send a Telegram message to all configured owner IDs."""

    settings = get_settings()
    owner_ids: Sequence[int] = settings.telegram_owner_ids or ()
    if not owner_ids:
        logger.debug("[owner_notify] Tidak ada owner yang terkonfigurasi.")
        return

    token = settings.owner_bot_token or settings.telegram_bot_token
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    store_prefix = f"[{settings.store_name}] "
    if not message.startswith(store_prefix):
        message = store_prefix + message

    close_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=10.0)
        close_client = True

    try:
        for owner_id in owner_ids:
            payload = {
                "chat_id": owner_id,
                "text": message,
                "disable_notification": disable_notification,
            }
            if parse_mode:
                payload["parse_mode"] = parse_mode
            try:
                response = await client.post(url, json=payload)
                if response.is_error:
                    logger.error(
                        "[owner_notify] Gagal mengirim ke owner %s: %s",
                        owner_id,
                        response.text,
                    )
            except httpx.HTTPError as exc:
                logger.error(
                    "[owner_notify] HTTP error saat kirim ke owner %s: %s",
                    owner_id,
                    exc,
                )
    finally:
        if close_client:
            await client.aclose()
