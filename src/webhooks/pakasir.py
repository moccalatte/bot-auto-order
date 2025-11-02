"""Handlers for Pakasir webhook callbacks."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any, Dict

from aiohttp import web

from src.core.config import get_settings
from src.core.telemetry import TelemetryTracker
from src.services.payment import PaymentService


logger = logging.getLogger(__name__)


def verify_signature(raw_body: bytes, signature: str | None, secret: str | None) -> bool:
    """Validate HMAC signature when secret is configured."""
    if not secret:
        return True
    if not signature:
        return False
    digest = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature)


async def handle_pakasir_webhook(
    request: web.Request,
    payment_service: PaymentService,
    telemetry: TelemetryTracker,
) -> web.Response:
    """Process Pakasir webhook request and update payment status."""
    settings = get_settings()
    raw_body = await request.read()
    signature = request.headers.get("X-Pakasir-Signature")

    if not verify_signature(raw_body, signature, settings.pakasir_webhook_secret):
        raise web.HTTPUnauthorized(text="Invalid signature")

    try:
        payload: Dict[str, Any] = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        logger.error("Invalid JSON payload: %s", exc)
        raise web.HTTPBadRequest(text="Invalid JSON")

    logger.info("📬 Pakasir webhook payload: %s", payload)

    status = payload.get("status")
    order_id = str(payload.get("order_id", ""))
    amount_cents = int(payload.get("amount", 0))

    if status == "completed":
        await payment_service.mark_payment_completed(order_id, amount_cents)
        await telemetry.increment("successful_transactions")
    elif status in {"failed", "expired", "cancelled"}:
        await payment_service.mark_payment_failed(order_id)
        await telemetry.increment("failed_transactions")
    else:
        logger.warning("Unhandled Pakasir status: %s", status)

    return web.json_response({"ok": True})
