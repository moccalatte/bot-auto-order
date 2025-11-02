"""Standalone aiohttp server for webhook endpoints."""

from __future__ import annotations

import argparse
import asyncio

import uvloop
from aiohttp import web

from src.core.config import get_settings
from src.core.logging import setup_logging
from src.core.telemetry import TelemetryTracker
from src.services.pakasir import PakasirClient
from src.services.payment import PaymentService
from src.services.postgres import get_pool
from src.webhooks.pakasir import handle_pakasir_webhook


def parse_args() -> argparse.Namespace:
    """Parse CLI options for webhook server."""
    parser = argparse.ArgumentParser(description="Webhook server for Pakasir callbacks")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9000)
    return parser.parse_args()


def create_app() -> web.Application:
    """Instantiate aiohttp application with webhook routes."""
    settings = get_settings()
    telemetry = TelemetryTracker()
    pakasir_client = PakasirClient()
    payment_service = PaymentService(pakasir_client=pakasir_client, telemetry=telemetry)

    app = web.Application()
    app["settings"] = settings
    app["telemetry"] = telemetry
    app["pakasir_client"] = pakasir_client
    app["payment_service"] = payment_service

    async def pakasir_handler(request: web.Request) -> web.Response:
        return await handle_pakasir_webhook(
            request,
            payment_service=payment_service,
            telemetry=telemetry,
        )

    app.router.add_post("/webhooks/pakasir", pakasir_handler)

    async def on_startup(app: web.Application) -> None:
        await telemetry.start()
        await get_pool()

    async def on_cleanup(app: web.Application) -> None:
        await telemetry.flush()
        await pakasir_client.aclose()
        pool = await get_pool()
        await pool.close()

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


def main() -> None:
    """Run aiohttp server."""
    args = parse_args()
    uvloop.install()
    setup_logging(service_name="webhook")
    app = create_app()
    web.run_app(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
