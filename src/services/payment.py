"""Payment orchestration layer."""

from __future__ import annotations

import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, Tuple
from uuid import uuid4, UUID

from src.core.audit import audit_log
from src.core.telemetry import TelemetryTracker
from src.core.currency import calculate_gateway_fee
from src.services.cart import Cart
from src.services.catalog import Product
from src.services.pakasir import PakasirClient
from src.services.owner_alerts import notify_owners
from src.services.postgres import get_pool
from src.services.users import upsert_user, update_balance
from src.services.terms import schedule_terms_notifications
from src.services.payment_messages import delete_payment_messages
from src.services.deposit import (
    create_deposit,
    get_deposit_by_gateway,
    update_deposit_status,
)
from src.services.product_content import (
    get_available_content,
    mark_content_as_used,
    get_order_contents,
)


logger = logging.getLogger(__name__)


def _parse_iso_datetime(iso_string: str | datetime | None) -> datetime | None:
    """Parse ISO 8601 datetime string to datetime object.

    Handles formats like:
    - "2025-11-06T02:59:36.377465708Z"
    - "2025-09-19T01:18:49.678622564Z"
    - "2025-09-10T08:07:02.819+07:00"

    If already a datetime, returns as-is. If None, returns None.
    """
    if iso_string is None or isinstance(iso_string, datetime):
        return iso_string

    if not isinstance(iso_string, str):
        logger.warning("Unexpected type for datetime parsing: %s", type(iso_string))
        return None

    try:
        # Try parsing with fromisoformat (Python 3.7+)
        # Handle 'Z' suffix by replacing with '+00:00'
        normalized = iso_string.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except (ValueError, TypeError) as exc:
        logger.error("Failed to parse ISO datetime '%s': %s", iso_string, exc)
        return None


class PaymentError(RuntimeError):
    """Raised when invoice creation fails."""


class PaymentService:
    """Coordinate order creation, invoice generation, and telemetry."""

    def __init__(
        self, pakasir_client: PakasirClient, telemetry: TelemetryTracker
    ) -> None:
        self._pakasir_client = pakasir_client
        self._telemetry = telemetry
        self._failure_lock = asyncio.Lock()
        self._consecutive_failures = 0
        self._alert_threshold = 3

    async def _register_failure(self, reason: str) -> None:
        async with self._failure_lock:
            self._consecutive_failures += 1
            counter = self._consecutive_failures
        logger.error("[payment] Gateway gagal #%s: %s", counter, reason)
        if counter >= self._alert_threshold:
            await notify_owners(
                "💥 Terjadi kegagalan pembayaran berturut-turut. Harap cek gateway Pakasir.",
            )

    async def _reset_failures(self) -> None:
        async with self._failure_lock:
            if self._consecutive_failures:
                logger.info(
                    "[payment] Reset counter kegagalan (sebelumnya %s).",
                    self._consecutive_failures,
                )
            self._consecutive_failures = 0

    async def create_invoice(
        self,
        *,
        telegram_user: Dict[str, str | int | None],
        cart: Cart,
        method: str = "qris",
    ) -> Tuple[str, Dict[str, object]]:
        """Create order, payment record, and request invoice from Pakasir."""
        if cart.total_items() == 0:
            raise PaymentError("Cart is empty.")

        logger.info("🛒 Creating order for user %s", telegram_user.get("id"))
        user_id = await upsert_user(
            telegram_id=int(telegram_user["id"]),
            username=telegram_user.get("username"),
            first_name=telegram_user.get("first_name"),
            last_name=telegram_user.get("last_name"),
        )

        total_cents = cart.total_cents()
        # Calculate fee for display only - Pakasir will add it automatically
        fee_cents = calculate_gateway_fee(total_cents) if method != "deposit" else 0
        payable_cents = total_cents + fee_cents
        gateway_order_id = f"tg{telegram_user['id']}-{uuid4().hex[:8]}"

        pool = await get_pool()
        async with pool.acquire() as connection:
            async with connection.transaction():
                order_row = await connection.fetchrow(
                    """
                    INSERT INTO orders (user_id, total_price_cents, status)
                    VALUES ($1, $2, 'awaiting_payment')
                    RETURNING id, created_at;
                    """,
                    user_id,
                    total_cents,
                )
                if order_row is None:
                    raise PaymentError("Failed to create order.")
                order_id = order_row["id"]

                for item in cart.items.values():
                    if item.quantity > item.product.stock:
                        raise PaymentError(
                            f"Stok tidak cukup untuk {item.product.name}."
                        )

                    await connection.execute(
                        """
                        INSERT INTO order_items (order_id, product_id, quantity, unit_price_cents)
                        VALUES ($1, $2, $3, $4);
                        """,
                        order_id,
                        item.product.id,
                        item.quantity,
                        item.product.price_cents,
                    )

                # Initialize payment record with expires_at placeholder
                await connection.execute(
                    """
                    INSERT INTO payments (
                        order_id,
                        gateway_order_id,
                        method,
                        status,
                        amount_cents,
                        fee_cents,
                        total_payment_cents,
                        created_at,
                        updated_at,
                        expires_at
                    )
                    VALUES ($1, $2, $3, 'created', $4, $5, $6, NOW(), NOW(), NULL);
                    """,
                    order_id,
                    gateway_order_id,
                    method,
                    total_cents,
                    fee_cents,
                    payable_cents,
                )

        if method == "deposit":
            # Catat pembayaran manual yang perlu verifikasi owner.
            await self._record_manual_payment(order_id, total_cents, telegram_user)
            payment_payload = {
                "method": "deposit",
                "note": "Menunggu verifikasi manual owner",
            }
        else:
            try:
                # Send only total_cents to Pakasir - they will add the fee automatically
                pakasir_response = await self._pakasir_client.create_transaction(
                    method,
                    gateway_order_id,
                    total_cents,
                )
            except Exception as exc:  # pragma: no cover - network failure
                await self._register_failure(str(exc))
                raise PaymentError(
                    "Gateway pembayaran sedang bermasalah, coba lagi sebentar lagi."
                ) from exc
            await self._reset_failures()
            payment_payload = pakasir_response.get("payment", {})

            # Save expires_at from Pakasir response
            expires_at_str = payment_payload.get("expired_at")
            if expires_at_str:
                # Parse ISO datetime string to datetime object for asyncpg
                expires_at = _parse_iso_datetime(expires_at_str)
                if expires_at:
                    pool = await get_pool()
                    async with pool.acquire() as connection:
                        await connection.execute(
                            """
                            UPDATE payments
                            SET expires_at = $2
                            WHERE gateway_order_id = $1;
                            """,
                            gateway_order_id,
                            expires_at,
                        )
                    logger.info(
                        "[payment] Saved expires_at for %s: %s",
                        gateway_order_id,
                        expires_at,
                    )
                else:
                    logger.warning(
                        "[payment] Failed to parse expires_at '%s' for order %s",
                        expires_at_str,
                        gateway_order_id,
                    )

        await self._telemetry.increment("carts_created")

        return gateway_order_id, {
            "order_id": str(order_id),
            "total_cents": total_cents,
            "fee_cents": fee_cents,
            "payable_cents": payable_cents,
            "payment": payment_payload,
            "payment_url": self._pakasir_client.build_payment_url(
                gateway_order_id, total_cents
            ),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    async def create_deposit_invoice(
        self, telegram_user: Dict[str, str | int | None], amount_cents: int
    ) -> Tuple[str, Dict[str, object]]:
        """Create QRIS deposit invoice."""
        if amount_cents <= 0:
            raise PaymentError("Deposit amount must be greater than zero.")

        logger.info("💰 Creating deposit for user %s", telegram_user.get("id"))
        user_id = await upsert_user(
            telegram_id=int(telegram_user["id"]),
            username=telegram_user.get("username"),
            first_name=telegram_user.get("first_name"),
            last_name=telegram_user.get("last_name"),
        )

        # Calculate fee for display only - Pakasir will add it automatically
        fee_cents = calculate_gateway_fee(amount_cents)
        payable_cents = amount_cents + fee_cents
        gateway_order_id = f"dp{telegram_user['id']}-{uuid4().hex[:8]}"

        try:
            # Send only amount_cents to Pakasir - they will add the fee automatically
            pakasir_response = await self._pakasir_client.create_transaction(
                "qris",
                gateway_order_id,
                amount_cents,
            )
        except Exception as exc:  # pragma: no cover - network failure
            await self._register_failure(str(exc))
            raise PaymentError(
                "Gateway pembayaran sedang bermasalah, coba lagi sebentar lagi."
            ) from exc

        await self._reset_failures()
        payment_payload = pakasir_response.get("payment", {})
        expires_at = _parse_iso_datetime(payment_payload.get("expired_at"))

        deposit_row = await create_deposit(
            user_id=user_id,
            amount_cents=amount_cents,
            fee_cents=fee_cents,
            payable_cents=payable_cents,
            method="qris",
            gateway_order_id=gateway_order_id,
            expires_at=expires_at,
        )

        return gateway_order_id, {
            "deposit_id": deposit_row.get("id"),
            "amount_cents": amount_cents,
            "fee_cents": fee_cents,
            "payable_cents": payable_cents,
            "payment": payment_payload,
            "payment_url": self._pakasir_client.build_payment_url(
                gateway_order_id, amount_cents
            ),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": payment_payload.get("expired_at"),
        }

    async def mark_payment_completed(
        self, gateway_order_id: str, amount_cents: int
    ) -> None:
        """Set payment and order status to completed."""
        pool = await get_pool()
        async with pool.acquire() as connection:
            async with connection.transaction():
                payment_row = await connection.fetchrow(
                    """
                    SELECT
                        order_id,
                        status,
                        amount_cents,
                        fee_cents,
                        total_payment_cents
                    FROM payments
                    WHERE gateway_order_id = $1
                    FOR UPDATE;
                    """,
                    gateway_order_id,
                )
                if payment_row is None:
                    logger.warning("Payment not found for %s", gateway_order_id)
                    raise PaymentError("Payment tidak ditemukan.")

                if payment_row["status"] == "completed":
                    logger.info(
                        "[payment_replay] Gateway %s sudah ditandai selesai, abaikan webhook ulang.",
                        gateway_order_id,
                    )
                    return

                stored_total = int(payment_row.get("total_payment_cents") or 0)
                if stored_total != amount_cents:
                    logger.error(
                        "[payment_mismatch] Amount gateway %s tidak cocok. stored=%s gateway=%s",
                        gateway_order_id,
                        stored_total,
                        amount_cents,
                    )
                    raise PaymentError("Nominal pembayaran tidak cocok.")

                order_id = payment_row["order_id"]
                order_row = await connection.fetchrow(
                    """
                    SELECT total_price_cents FROM orders WHERE id = $1 LIMIT 1;
                    """,
                    order_id,
                )
                base_amount = int(payment_row.get("amount_cents") or 0)
                if (
                    order_row
                    and int(order_row["total_price_cents"] or 0) != base_amount
                ):
                    logger.error(
                        "[payment_mismatch] Order %s total tidak sesuai dengan pembayaran %s",
                        order_id,
                        gateway_order_id,
                    )
                    raise PaymentError("Nominal order tidak sesuai.")

                await connection.execute(
                    """
                    UPDATE payments
                    SET status = 'completed',
                        updated_at = NOW()
                    WHERE gateway_order_id = $1;
                    """,
                    gateway_order_id,
                )

                await connection.execute(
                    """
                    UPDATE orders
                    SET status = 'paid',
                        updated_at = NOW()
                    WHERE id = $1;
                    """,
                    order_id,
                )

                # Allocate product contents for the order
                order_items = await connection.fetch(
                    """
                    SELECT product_id, quantity
                    FROM order_items
                    WHERE order_id = $1;
                    """,
                    order_id,
                )

                # Process outside transaction to avoid deadlocks
                pass  # Content allocation will happen after transaction

        # Allocate product contents after transaction completes
        pool = await get_pool()
        async with pool.acquire() as connection:
            for item in order_items:
                product_id = item["product_id"]
                quantity = item["quantity"]

                # Get available contents for this product
                available_contents = await get_available_content(product_id, quantity)

                if len(available_contents) < quantity:
                    logger.error(
                        "[stock_error] Insufficient content stock for product %s. "
                        "Required: %s, Available: %s for order %s",
                        product_id,
                        quantity,
                        len(available_contents),
                        order_id,
                    )
                    # Still mark what we have as used
                    for content in available_contents:
                        await mark_content_as_used(content["id"], UUID(str(order_id)))
                else:
                    # Mark all required contents as used
                    for content in available_contents:
                        await mark_content_as_used(content["id"], UUID(str(order_id)))

                # Increment sold count for product
                await connection.execute(
                    """
                    UPDATE products
                    SET sold_count = sold_count + $2,
                        updated_at = NOW()
                    WHERE id = $1;
                    """,
                    product_id,
                    quantity,
                )

        # Send product contents to customer
        await self._send_product_contents_to_customer(str(order_id))

        await schedule_terms_notifications(str(order_id))
        await self._telemetry.increment("successful_transactions")
        logger.info(
            "[payment_completed] Order %s sukses dari gateway %s",
            order_id,
            gateway_order_id,
        )
        audit_log(
            actor_id=None,
            action="payment.completed",
            details={
                "gateway_order_id": gateway_order_id,
                "order_id": int(order_id),
                "amount_cents": amount_cents,
            },
        )
        await delete_payment_messages(gateway_order_id)

        # Notify admins about successful payment
        await self._notify_admins_payment_success(gateway_order_id, str(order_id))

    async def mark_payment_failed(self, gateway_order_id: str) -> None:
        """Mark payment as failed/expired."""
        pool = await get_pool()
        order_id: int | None = None
        async with pool.acquire() as connection:
            async with connection.transaction():
                payment_row = await connection.fetchrow(
                    """
                    SELECT order_id, status
                    FROM payments
                    WHERE gateway_order_id = $1
                    FOR UPDATE;
                    """,
                    gateway_order_id,
                )
                if payment_row is None:
                    logger.warning("Payment not found for %s", gateway_order_id)
                    return

                if payment_row["status"] == "failed":
                    logger.info(
                        "[payment_replay] Payment %s sudah gagal sebelumnya.",
                        gateway_order_id,
                    )
                    return

                order_id = payment_row["order_id"]

                await connection.execute(
                    """
                    UPDATE payments
                    SET status = 'failed',
                        updated_at = NOW()
                    WHERE gateway_order_id = $1;
                    """,
                    gateway_order_id,
                )

                await connection.execute(
                    """
                    UPDATE orders
                    SET status = 'cancelled',
                        updated_at = NOW()
                    WHERE id = $1 AND status <> 'paid';
                    """,
                    order_id,
                )

                order_items = await connection.fetch(
                    """
                    SELECT product_id, quantity
                    FROM order_items
                    WHERE order_id = $1;
                    """,
                    order_id,
                )
                for item in order_items:
                    await connection.execute(
                        """
                        UPDATE products
                        SET stock = stock + $2,
                            updated_at = NOW()
                        WHERE id = $1;
                        """,
                        item["product_id"],
                        item["quantity"],
                    )
                logger.info(
                    "[payment_failed] Restock order %s karena payment %s gagal.",
                    order_id,
                    gateway_order_id,
                )
        await self._telemetry.increment("failed_transactions")
        audit_log(
            actor_id=None,
            action="payment.failed",
            details={
                "gateway_order_id": gateway_order_id,
                "order_id": order_id,
            },
        )

    async def _send_product_contents_to_customer(self, order_id: str) -> None:
        """Send product contents and SNK to customer after successful payment."""
        try:
            from telegram import Bot
            from telegram.constants import ParseMode
            from src.core.config import get_settings

            settings = get_settings()
            bot = Bot(token=settings.telegram_bot_token)

            # Get order and user details
            pool = await get_pool()
            async with pool.acquire() as connection:
                order_data = await connection.fetchrow(
                    """
                    SELECT o.id, u.telegram_id, u.first_name
                    FROM orders o
                    JOIN users u ON o.user_id = u.id
                    WHERE o.id = $1;
                    """,
                    order_id,
                )

                if not order_data:
                    logger.error("[product_delivery] Order %s not found", order_id)
                    return

                telegram_id = order_data["telegram_id"]
                customer_name = order_data["first_name"] or "Customer"

                # Get product contents for this order
                contents = await get_order_contents(UUID(order_id))

                if not contents:
                    logger.warning(
                        "[product_delivery] No contents found for order %s", order_id
                    )
                    return

                # Build message with all product contents
                message_parts = [
                    f"🎉 <b>Pembayaran Berhasil, {customer_name}!</b>\n",
                    "✅ Terima kasih sudah berbelanja di toko kami.\n",
                    f"📦 <b>Order ID:</b> <code>{order_id}</code>\n\n",
                    "━━━━━━━━━━━━━━━━━━━━\n",
                ]

                for idx, content_data in enumerate(contents, 1):
                    product_name = content_data["product_name"]
                    content_text = content_data["content"]

                    message_parts.append(f"📦 <b>Produk {idx}: {product_name}</b>\n")
                    message_parts.append(f"<pre>{content_text}</pre>\n")
                    message_parts.append("━━━━━━━━━━━━━━━━━━━━\n")

                # Check if products have SNK
                snk_rows = await connection.fetch(
                    """
                    SELECT DISTINCT pt.content
                    FROM order_items oi
                    JOIN product_terms pt ON pt.product_id = oi.product_id
                    WHERE oi.order_id = $1;
                    """,
                    order_id,
                )

                if snk_rows:
                    message_parts.append("\n📜 <b>Syarat & Ketentuan:</b>\n")
                    for snk_row in snk_rows:
                        message_parts.append(f"{snk_row['content']}\n")
                    message_parts.append(
                        "\n⚠️ <b>WAJIB BACA DAN IKUTI S&K DI ATAS!</b>\n"
                    )

                message_parts.append(
                    "\n💬 Jika ada kendala, hubungi admin ya. Terima kasih! 😊"
                )

                full_message = "".join(message_parts)

                # Send to customer
                await bot.send_message(
                    chat_id=telegram_id,
                    text=full_message,
                    parse_mode=ParseMode.HTML,
                )

                logger.info(
                    "[product_delivery] Sent %d product contents to user %s for order %s",
                    len(contents),
                    telegram_id,
                    order_id,
                )

        except Exception as exc:
            logger.error(
                "[product_delivery] Failed to send contents for order %s: %s",
                order_id,
                exc,
                exc_info=True,
            )

    async def _notify_admins_payment_success(
        self, gateway_order_id: str, order_id: str
    ) -> None:
        """Send notification to admins when order payment is successful."""
        try:
            from telegram import Bot
            from telegram.constants import ParseMode
            from src.core.config import get_settings
            from src.core.currency import format_rupiah

            settings = get_settings()
            bot = Bot(token=settings.telegram_bot_token)

            # Get order details
            pool = await get_pool()
            async with pool.acquire() as connection:
                order_data = await connection.fetchrow(
                    """
                    SELECT
                        o.total_price_cents,
                        u.telegram_id,
                        u.username,
                        u.first_name,
                        u.last_name
                    FROM orders o
                    JOIN users u ON o.user_id = u.id
                    WHERE o.id = $1;
                    """,
                    order_id,
                )

                if not order_data:
                    return

                # Get order items
                order_items = await connection.fetch(
                    """
                    SELECT
                        oi.quantity,
                        p.name
                    FROM order_items oi
                    JOIN products p ON oi.product_id = p.id
                    WHERE oi.order_id = $1;
                    """,
                    order_id,
                )

            customer_name = (
                order_data["first_name"] or order_data["username"] or "Customer"
            )
            username = f"@{order_data['username']}" if order_data["username"] else "-"
            telegram_id = order_data["telegram_id"]
            total_text = format_rupiah(order_data["total_price_cents"])

            products_list = ", ".join(
                [f"{item['quantity']}x {item['name']}" for item in order_items]
            )

            message_text = (
                f"✅ <b>Pembayaran Berhasil!</b>\n\n"
                f"<b>Customer:</b> {customer_name}\n"
                f"<b>ID Telegram:</b> {telegram_id}\n"
                f"<b>Username:</b> {username}\n"
                f"<b>Produk:</b> {products_list}\n"
                f"<b>Total:</b> {total_text}\n"
                f"<b>Gateway ID:</b> <code>{gateway_order_id}</code>\n"
                f"<b>Order ID:</b> <code>{order_id}</code>\n\n"
                "📦 <b>Pesanan sudah diproses dan produk dikirim ke customer.</b>"
            )

            # Send to all admins
            admin_ids = settings.telegram_admin_ids + settings.telegram_owner_ids
            for admin_id in admin_ids:
                try:
                    await bot.send_message(
                        chat_id=admin_id,
                        text=message_text,
                        parse_mode=ParseMode.HTML,
                    )
                except Exception as exc:
                    logger.warning(
                        "[payment_success_notif] Failed to notify admin %s: %s",
                        admin_id,
                        exc,
                    )
        except Exception as exc:
            logger.error("[payment_success_notif] Error sending notification: %s", exc)

    async def _notify_admins_deposit_success(
        self,
        gateway_order_id: str,
        deposit_id: int,
        user_telegram_id: int,
        amount_cents: int,
    ) -> None:
        """Send notification to admins when deposit is successful."""
        try:
            from telegram import Bot
            from telegram.constants import ParseMode
            from src.core.config import get_settings
            from src.core.currency import format_rupiah

            settings = get_settings()
            bot = Bot(token=settings.telegram_bot_token)

            # Get user details
            pool = await get_pool()
            async with pool.acquire() as connection:
                user_data = await connection.fetchrow(
                    """
                    SELECT username, first_name, last_name
                    FROM users
                    WHERE telegram_id = $1;
                    """,
                    user_telegram_id,
                )

            if not user_data:
                return

            customer_name = (
                user_data["first_name"] or user_data["username"] or "Customer"
            )
            username = f"@{user_data['username']}" if user_data["username"] else "-"
            amount_text = format_rupiah(amount_cents)

            message_text = (
                f"✅ <b>Deposit Berhasil!</b>\n\n"
                f"<b>Customer:</b> {customer_name}\n"
                f"<b>ID Telegram:</b> {user_telegram_id}\n"
                f"<b>Username:</b> {username}\n"
                f"<b>Nominal:</b> {amount_text}\n"
                f"<b>Gateway ID:</b> <code>{gateway_order_id}</code>\n"
                f"<b>Deposit ID:</b> {deposit_id}\n\n"
                "💰 <b>Saldo customer sudah ditambahkan.</b>"
            )

            # Send to all admins
            admin_ids = settings.telegram_admin_ids + settings.telegram_owner_ids
            for admin_id in admin_ids:
                try:
                    await bot.send_message(
                        chat_id=admin_id,
                        text=message_text,
                        parse_mode=ParseMode.HTML,
                    )
                except Exception as exc:
                    logger.warning(
                        "[deposit_success_notif] Failed to notify admin %s: %s",
                        admin_id,
                        exc,
                    )
        except Exception as exc:
            logger.error("[deposit_success_notif] Error sending notification: %s", exc)

    async def mark_deposit_completed(
        self, gateway_order_id: str, amount_cents: int
    ) -> Dict[str, Any]:
        """Mark deposit as completed and credit user balance."""
        deposit = await get_deposit_by_gateway(gateway_order_id)
        if deposit is None:
            raise PaymentError("Deposit tidak ditemukan.")

        current_status = str(deposit.get("status") or "")
        payable_expected = int(deposit.get("payable_cents") or 0)
        if payable_expected and payable_expected != amount_cents:
            raise PaymentError("Nominal deposit tidak cocok.")

        if current_status == "completed":
            logger.info(
                "[deposit_replay] Deposit %s sudah selesai, abaikan webhook ulang.",
                gateway_order_id,
            )
            return deposit

        updated = await update_deposit_status(gateway_order_id, "completed")
        if updated is None:
            logger.warning(
                "[deposit_status] Deposit %s tidak ditemukan saat update status.",
                gateway_order_id,
            )
            return deposit

        credit_amount = int(updated.get("amount_cents") or 0)
        if credit_amount > 0:
            await update_balance(int(updated["user_id"]), credit_amount)
        await self._telemetry.increment("successful_transactions")
        logger.info(
            "[deposit_completed] Deposit %s selesai (%s rupiah).",
            gateway_order_id,
            credit_amount,
        )
        audit_log(
            actor_id=int(updated.get("user_id") or 0),
            action="deposit.completed",
            details={
                "gateway_order_id": gateway_order_id,
                "amount_cents": credit_amount,
                "fee_cents": int(updated.get("fee_cents") or 0),
            },
        )
        await delete_payment_messages(gateway_order_id)

        # Notify admins about successful deposit
        await self._notify_admins_deposit_success(
            gateway_order_id, int(updated["id"]), int(updated["user_id"]), credit_amount
        )

        return updated

    async def mark_deposit_failed(self, gateway_order_id: str) -> None:
        """Mark deposit as failed or expired."""
        current = await get_deposit_by_gateway(gateway_order_id)
        if current is None:
            logger.warning(
                "[deposit_failed] Deposit %s tidak ditemukan saat penandaan gagal.",
                gateway_order_id,
            )
            return
        if str(current.get("status") or "") == "failed":
            logger.info(
                "[deposit_replay] Deposit %s sudah ditandai gagal sebelumnya.",
                gateway_order_id,
            )
            return
        deposit = await update_deposit_status(gateway_order_id, "failed")
        if deposit:
            await self._telemetry.increment("failed_transactions")
            logger.info("[deposit_failed] Deposit %s ditandai gagal.", gateway_order_id)
            audit_log(
                actor_id=int(deposit.get("user_id") or 0),
                action="deposit.failed",
                details={
                    "gateway_order_id": gateway_order_id,
                    "amount_cents": int(deposit.get("amount_cents") or 0),
                },
            )

    async def _record_manual_payment(
        self,
        order_id: int,
        amount_cents: int,
        telegram_user: Dict[str, str | int | None],
    ) -> None:
        """Catat pembayaran manual/deposit agar owner dapat memverifikasi."""

        pool = await get_pool()
        async with pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS payment_manual_reviews (
                        id BIGSERIAL PRIMARY KEY,
                        order_id BIGINT NOT NULL,
                        telegram_user_id BIGINT,
                        telegram_username TEXT,
                        amount_cents BIGINT NOT NULL,
                        note TEXT,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    );
                    """
                )

                await connection.execute(
                    """
                    INSERT INTO payment_manual_reviews (
                        order_id,
                        telegram_user_id,
                        telegram_username,
                        amount_cents,
                        note
                    )
                    VALUES ($1, $2, $3, $4, 'Manual deposit pending owner verification');
                    """,
                    order_id,
                    telegram_user.get("id"),
                    telegram_user.get("username"),
                    amount_cents,
                )

                await connection.execute(
                    """
                    UPDATE orders
                    SET status = 'pending_manual',
                        updated_at = NOW()
                    WHERE id = $1;
                    """,
                    order_id,
                )

        logger.info(
            "[manual_payment_pending] Order %s menunggu verifikasi owner (deposit/manual).",
            order_id,
        )
        audit_log(
            actor_id=telegram_user.get("id"),
            action="payment.manual_pending",
            details={
                "order_id": order_id,
                "amount_cents": amount_cents,
                "telegram_username": telegram_user.get("username"),
            },
        )
