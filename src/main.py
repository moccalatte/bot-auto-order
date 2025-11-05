"""Entry point for bot-order Telegram bot."""

from __future__ import annotations

import argparse
import logging
import os

import uvloop
from telegram.ext import Application

from src.bot import handlers
from src.core.config import get_settings
from src.core.logging import setup_logging
from src.core.telemetry import TelemetryTracker
from src.core.scheduler import register_scheduled_jobs
from src.services.pakasir import PakasirClient
from src.services.postgres import get_pool


logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Bot Auto Order Telegram")
    parser.add_argument(
        "--mode",
        choices=("auto", "polling", "webhook"),
        default="auto",
        help="Run mode: polling, webhook, or auto (default).",
    )
    parser.add_argument(
        "--webhook",
        action="store_true",
        help="(deprecated) Equivalent to --mode=webhook.",
    )
    parser.add_argument("--webhook-url", help="Public HTTPS URL for Telegram webhook")
    parser.add_argument("--listen", default="0.0.0.0", help="Webhook listen address")
    parser.add_argument("--port", type=int, default=8080, help="Webhook listen port")
    parser.add_argument("--path", default="telegram", help="Webhook URL path")
    return parser.parse_args()


async def _post_init(application: Application) -> None:
    """Executed after Application initialises."""
    telemetry: TelemetryTracker = application.bot_data["telemetry"]
    await telemetry.start()
    await get_pool()
    logger.info("✅ Bot initialised.")


async def _post_shutdown(application: Application) -> None:
    """Executed during application shutdown."""
    telemetry: TelemetryTracker = application.bot_data["telemetry"]
    await telemetry.flush()
    pakasir_client: PakasirClient = application.bot_data["pakasir_client"]
    await pakasir_client.aclose()
    pool = await get_pool()
    await pool.close()
    logger.info("👋 Shutdown complete.")


def main() -> None:
    """Program entry point."""
    args = parse_args()
    uvloop.install()
    settings = get_settings()
    setup_logging()

    mode = args.mode
    if args.webhook:
        logger.warning("--webhook is deprecated; prefer --mode=webhook.")
        mode = "webhook"

    telemetry = TelemetryTracker()
    pakasir_client = PakasirClient()

    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )

    handlers.setup_bot_data(application, pakasir_client, telemetry)
    handlers.register(application)
    register_scheduled_jobs(application)

    webhook_url = args.webhook_url or os.environ.get("TELEGRAM_WEBHOOK_URL")
    listen = args.listen
    port = args.port
    url_path = args.path

    def _run_polling() -> None:
        logger.info("▶️ Starting bot in polling mode.")
        application.run_polling()

    def _run_webhook(url: str) -> None:
        resolved = url.rstrip("/") + f"/{url_path}"
        logger.info(
            "🌐 Starting bot in webhook mode. listen=%s port=%s url=%s",
            listen,
            port,
            resolved,
        )
        application.run_webhook(
            listen=listen,
            port=port,
            url_path=url_path,
            webhook_url=resolved,
        )

    if mode == "polling":
        _run_polling()
        return

    if mode == "webhook":
        if not webhook_url:
            raise SystemExit(
                "Webhook mode requires --webhook-url or TELEGRAM_WEBHOOK_URL."
            )
        _run_webhook(webhook_url)
        return

    # auto mode
    if webhook_url:
        try:
            _run_webhook(webhook_url)
            return
        except Exception as exc:  # pragma: no cover - startup failure fallback
            logger.exception(
                "Webhook startup failed (%s). Falling back to polling mode.", exc
            )
    else:
        logger.info("Webhook URL not provided; defaulting to polling mode.")

    _run_polling()


if __name__ == "__main__":
    main()
