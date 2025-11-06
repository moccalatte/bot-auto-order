"""Payment orchestration layer."""

from __future__ import annotations

import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, Tuple
from uuid import uuid4

from src.core.audit import audit_log
from src.core.telemetry import TelemetryTracker
from src.services.cart import Cart
from src.services.catalog import Product
from src.services.pakasir import PakasirClient
from src.services.owner_alerts import notify_owners
from src.services.postgres import get_pool
from src.services.users import upsert_user
from src.services.terms import schedule_terms_notifications
from src.services.payment_messages import delete_payment_messages


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
                        total_payment_cents,
                        created_at,
                        updated_at,
                        expires_at
                    )
                    VALUES ($1, $2, $3, 'created', $4, $4, NOW(), NOW(), NULL);
                    """,
                    order_id,
                    gateway_order_id,
                    method,
                    total_cents,
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
            "payment": payment_payload,
            "payment_url": self._pakasir_client.build_payment_url(
                gateway_order_id, total_cents
            ),
            "created_at": datetime.now(timezone.utc).isoformat(),
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
                    SELECT order_id, status, amount_cents
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

                stored_amount = int(payment_row.get("amount_cents") or 0)
                if stored_amount != amount_cents:
                    logger.error(
                        "[payment_mismatch] Amount gateway %s tidak cocok. stored=%s gateway=%s",
                        gateway_order_id,
                        stored_amount,
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
                if (
                    order_row
                    and int(order_row["total_price_cents"] or 0) != amount_cents
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

                # Deduct stock only when payment is completed successfully
                order_items = await connection.fetch(
                    """
                    SELECT product_id, quantity
                    FROM order_items
                    WHERE order_id = $1;
                    """,
                    order_id,
                )
                for item in order_items:
                    update_result = await connection.execute(
                        """
                        UPDATE products
                        SET stock = stock - $2,
                            updated_at = NOW()
                        WHERE id = $1 AND stock >= $2;
                        """,
                        item["product_id"],
                        item["quantity"],
                    )
                    if update_result == "UPDATE 0":
                        logger.error(
                            "[stock_error] Insufficient stock for product %s during payment completion for order %s",
                            item["product_id"],
                            order_id,
                        )
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
