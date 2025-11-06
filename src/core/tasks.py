"""Fungsi job terjadwal untuk health-check dan backup."""

from __future__ import annotations

import asyncio
import logging
from argparse import Namespace
from datetime import datetime, timezone

from telegram.ext import ContextTypes
from telegram.error import TelegramError

from src.core.config import get_settings
from src.tools.healthcheck import run_healthcheck
from src.tools.backup_manager import create_backup


logger = logging.getLogger(__name__)


async def healthcheck_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Jalankan health-check periodik."""

    try:
        await run_healthcheck(configure_logging=False)
    except Exception as exc:  # pragma: no cover - observability
        logger.exception("Health-check job gagal: %s", exc)


async def backup_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Jalankan backup terenkripsi secara berkala."""

    settings = get_settings()
    offsite = settings.backup_automatic_offsite
    args = Namespace(offsite=offsite)
    try:
        await asyncio.to_thread(create_backup, args)
    except SystemExit:
        # create_backup bisa memanggil SystemExit jika env tidak lengkap.
        logger.warning(
            "Backup job dilewati, BACKUP_ENCRYPTION_PASSWORD mungkin belum di-set."
        )
    except Exception as exc:  # pragma: no cover - observability
        logger.exception("Backup job gagal: %s", exc)


async def check_expired_payments_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Monitor dan handle pembayaran yang expired."""
    from src.services.postgres import get_pool
    from src.services.payment import PaymentService

    try:
        pool = await get_pool()
        async with pool.acquire() as connection:
            # Find payments that are expired but not yet marked as failed
            expired_payments = await connection.fetch(
                """
                SELECT
                    p.id,
                    p.gateway_order_id,
                    p.order_id,
                    p.amount_cents,
                    p.expires_at,
                    o.user_id,
                    u.telegram_id,
                    u.username
                FROM payments p
                JOIN orders o ON p.order_id = o.id
                JOIN users u ON o.user_id = u.id
                WHERE p.status IN ('created', 'waiting')
                  AND p.expires_at IS NOT NULL
                  AND p.expires_at < NOW()
                LIMIT 10;
                """
            )

            if not expired_payments:
                return

            logger.info(
                "[expired_payments] Found %d expired payments to process",
                len(expired_payments),
            )

            # Get payment service from bot_data
            payment_service: PaymentService = context.application.bot_data.get(
                "payment_service"
            )
            if not payment_service:
                logger.error("[expired_payments] PaymentService not found in bot_data")
                return

            for payment in expired_payments:
                gateway_order_id = payment["gateway_order_id"]
                telegram_id = payment["telegram_id"]
                username = payment.get("username") or "User"

                try:
                    # Mark payment as failed/expired
                    await payment_service.mark_payment_failed(gateway_order_id)

                    # Send notification to user
                    await context.bot.send_message(
                        chat_id=telegram_id,
                        text=(
                            f"⏰ <b>Pembayaran Kedaluwarsa</b>\n\n"
                            f"💳 ID Transaksi: <code>{gateway_order_id}</code>\n\n"
                            f"⚠️ Maaf, waktu pembayaran sudah habis.\n"
                            f"Pesanan kamu telah dibatalkan secara otomatis.\n\n"
                            f"🔄 Silakan buat pesanan baru jika masih ingin membeli.\n"
                            f"💬 Hubungi admin jika ada pertanyaan."
                        ),
                        parse_mode="HTML",
                    )

                    logger.info(
                        "[expired_payments] Notified user %s about expired payment %s",
                        telegram_id,
                        gateway_order_id,
                    )

                except TelegramError as exc:
                    logger.warning(
                        "[expired_payments] Failed to notify user %s: %s",
                        telegram_id,
                        exc,
                    )
                except Exception as exc:
                    logger.exception(
                        "[expired_payments] Error processing payment %s: %s",
                        gateway_order_id,
                        exc,
                    )

                # Small delay to avoid rate limiting
                await asyncio.sleep(0.2)

    except Exception as exc:
        logger.exception("[expired_payments] Job failed: %s", exc)
