"""Fungsi job terjadwal untuk health-check dan backup."""

from __future__ import annotations

import asyncio
import logging
from typing import Dict
from argparse import Namespace
from datetime import datetime, timezone

from telegram.ext import ContextTypes
from telegram.error import TelegramError
from telegram.constants import ParseMode

from src.core.config import get_settings
from src.tools.healthcheck import run_healthcheck
from src.tools.backup_manager import create_backup
from src.services.payment_messages import (
    fetch_payment_messages,
    delete_payment_messages,
)
from src.core.currency import format_rupiah
from src.services.deposit import list_expired_deposits


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
                    p.total_payment_cents,
                    p.fee_cents,
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

            async def _remove_logged_message(
                entry: Dict[str, object], fallback_text: str | None
            ) -> bool:
                chat_id = int(entry["chat_id"])
                message_id = int(entry["message_id"])
                message_kind = str(entry.get("message_kind") or "text")
                try:
                    await context.bot.delete_message(
                        chat_id=chat_id, message_id=message_id
                    )
                    return True
                except TelegramError as exc:
                    if fallback_text:
                        try:
                            if message_kind == "photo":
                                await context.bot.edit_message_caption(
                                    chat_id=chat_id,
                                    message_id=message_id,
                                    caption=fallback_text,
                                    parse_mode=ParseMode.HTML,
                                )
                            else:
                                await context.bot.edit_message_text(
                                    chat_id=chat_id,
                                    message_id=message_id,
                                    text=fallback_text,
                                    parse_mode=ParseMode.HTML,
                                )
                            return True
                        except TelegramError as inner_exc:
                            logger.warning(
                                "[expired_payments] Gagal mengubah pesan %s (%s): %s",
                                message_id,
                                message_kind,
                                inner_exc,
                            )
                    logger.warning(
                        "[expired_payments] Gagal menghapus pesan %s (%s): %s",
                        message_id,
                        entry.get("role"),
                        exc,
                    )
                    return False

            for payment in expired_payments:
                gateway_order_id = payment["gateway_order_id"]
                order_id = str(payment["order_id"])
                amount_cents = int(
                    payment.get("total_payment_cents")
                    or payment.get("amount_cents")
                    or 0
                )
                telegram_id = payment["telegram_id"]
                username = payment.get("username") or "User"
                user_cancel_message = (
                    "❌ <b>Pesanan Dibatalkan</b>\n"
                    f"<code>{gateway_order_id}</code>\n\n"
                    "⏰ Waktu pembayaran habis sehingga pesanan dibatalkan otomatis.\n"
                    "📦 Stok sudah dikembalikan dan order ditutup.\n\n"
                    "🔄 Silakan buat pesanan baru jika masih ingin melanjutkan.\n"
                    "💬 Hubungi admin jika memerlukan bantuan."
                )
                try:
                    # Mark payment as failed/expired
                    await payment_service.mark_payment_failed(gateway_order_id)

                    # Send notification to user
                    await context.bot.send_message(
                        chat_id=telegram_id,
                        text=user_cancel_message,
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

                try:
                    message_entries = await fetch_payment_messages(gateway_order_id)
                    if message_entries:
                        total_payment_cents = int(
                            payment.get("total_payment_cents") or amount_cents
                        )
                        amount_text = format_rupiah(total_payment_cents)
                        username_display = (
                            f"@{username}"
                            if username and not username.startswith("@")
                            else username or "-"
                        )
                        admin_cancellation_text = (
                            "❌ <b>Pesanan Dibatalkan (Expired)</b>\n\n"
                            f"<b>Gateway ID:</b> <code>{gateway_order_id}</code>\n"
                            f"<b>Order ID:</b> <code>{order_id}</code>\n"
                            f"<b>Nominal:</b> {amount_text}\n"
                            f"<b>User:</b> {username_display or '-'} (ID {telegram_id})\n\n"
                            "⏰ Pembayaran tidak selesai dalam batas waktu.\n"
                            "📦 Stok dan status order sudah dipulihkan otomatis."
                        )

                        for entry in message_entries:
                            role = str(entry.get("role") or "")
                            if role == "user_invoice":
                                await _remove_logged_message(entry, user_cancel_message)
                            elif role == "admin_order_alert":
                                await _remove_logged_message(
                                    entry, admin_cancellation_text
                                )
                                await context.bot.send_message(
                                    chat_id=int(entry["chat_id"]),
                                    text=admin_cancellation_text,
                                    parse_mode=ParseMode.HTML,
                                )
                        await delete_payment_messages(gateway_order_id)
                except Exception as exc:  # pragma: no cover - defensive cleanup
                    logger.warning(
                        "[expired_payments] Cleanup pesan gagal untuk %s: %s",
                        gateway_order_id,
                        exc,
                    )

                # Small delay to avoid rate limiting
                await asyncio.sleep(0.2)

            expired_deposits = await list_expired_deposits()
            if expired_deposits:
                logger.info(
                    "[expired_deposits] Found %d expired deposits to process",
                    len(expired_deposits),
                )

            for deposit in expired_deposits:
                gateway_order_id = deposit.get("gateway_order_id")
                if not gateway_order_id:
                    continue
                telegram_id = int(deposit.get("telegram_id") or 0)
                username = deposit.get("username") or "User"
                amount_cents = int(deposit.get("payable_cents") or 0)

                user_cancel_message = (
                    "❌ <b>Deposit Dibatalkan</b>\n"
                    f"<code>{gateway_order_id}</code>\n\n"
                    "⏰ Waktu pembayaran habis sehingga deposit dibatalkan otomatis.\n"
                    "Saldo kamu belum berubah.\n\n"
                    "🔄 Buat permintaan deposit baru jika masih ingin top-up."
                )

                try:
                    await payment_service.mark_deposit_failed(gateway_order_id)
                except Exception as exc:
                    logger.exception(
                        "[expired_deposits] Error marking deposit %s as failed: %s",
                        gateway_order_id,
                        exc,
                    )
                    continue

                try:
                    await context.bot.send_message(
                        chat_id=telegram_id,
                        text=user_cancel_message,
                        parse_mode=ParseMode.HTML,
                    )
                except TelegramError as exc:
                    logger.warning(
                        "[expired_deposits] Failed to notify user %s: %s",
                        telegram_id,
                        exc,
                    )

                try:
                    message_entries = await fetch_payment_messages(gateway_order_id)
                    if message_entries:
                        amount_text = format_rupiah(amount_cents)
                        username_display = (
                            f"@{username}"
                            if username and not username.startswith("@")
                            else username or "-"
                        )
                        admin_deposit_text = (
                            "❌ <b>Deposit Dibatalkan (Expired)</b>\n\n"
                            f"<b>Gateway ID:</b> <code>{gateway_order_id}</code>\n"
                            f"<b>Nominal Dibayar:</b> {amount_text}\n"
                            f"<b>User:</b> {username_display or '-'} (ID {telegram_id})\n\n"
                            "⏰ Pembayaran deposit tidak selesai tepat waktu.\n"
                            "Saldo pengguna tidak berubah."
                        )
                        for entry in message_entries:
                            role = str(entry.get("role") or "")
                            if role == "user_deposit":
                                await _remove_logged_message(entry, user_cancel_message)
                            elif role == "admin_deposit_alert":
                                await _remove_logged_message(entry, admin_deposit_text)
                                await context.bot.send_message(
                                    chat_id=int(entry["chat_id"]),
                                    text=admin_deposit_text,
                                    parse_mode=ParseMode.HTML,
                                )
                        await delete_payment_messages(gateway_order_id)
                except Exception as exc:
                    logger.warning(
                        "[expired_deposits] Cleanup pesan gagal untuk %s: %s",
                        gateway_order_id,
                        exc,
                    )
                await asyncio.sleep(0.2)

    except Exception as exc:
        logger.exception("[expired_payments] Job failed: %s", exc)
