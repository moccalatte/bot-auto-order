"""Entry point for bot-order Telegram bot."""

from __future__ import annotations

import argparse
import asyncio
import logging

import uvloop
from telegram.ext import Application

from src.bot import handlers
from src.core.config import get_settings
from src.core.logging import setup_logging
from src.core.telemetry import TelemetryTracker
from src.services.pakasir import PakasirClient
from src.services.postgres import get_pool


logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Bot Auto Order Telegram")
    parser.add_argument("--webhook", action="store_true", help="Run using webhook mode")
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

    if args.webhook:
        if not args.webhook_url:
            raise SystemExit("Webhook mode requires --webhook-url.")
        application.run_webhook(
            listen=args.listen,
            port=args.port,
            url_path=args.path,
            webhook_url=args.webhook_url.rstrip("/") + f"/{args.path}",
        )
    else:
        application.run_polling()


if __name__ == "__main__":
    main()
