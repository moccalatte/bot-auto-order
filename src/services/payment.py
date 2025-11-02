"""Payment orchestration layer."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Tuple
from uuid import uuid4

from src.core.telemetry import TelemetryTracker
from src.services.cart import Cart
from src.services.catalog import Product
from src.services.pakasir import PakasirClient
from src.services.postgres import get_pool
from src.services.users import upsert_user


logger = logging.getLogger(__name__)


class PaymentError(RuntimeError):
    """Raised when invoice creation fails."""


class PaymentService:
    """Coordinate order creation, invoice generation, and telemetry."""

    def __init__(self, pakasir_client: PakasirClient, telemetry: TelemetryTracker) -> None:
        self._pakasir_client = pakasir_client
        self._telemetry = telemetry

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
                        updated_at
                    )
                    VALUES ($1, $2, $3, 'created', $4, $4, NOW(), NOW());
                    """,
                    order_id,
                    gateway_order_id,
                    method,
                    total_cents,
                )

        pakasir_response = await self._pakasir_client.create_transaction(
            method,
            gateway_order_id,
            total_cents,
        )

        await self._telemetry.increment("carts_created")

        payment_payload = pakasir_response.get("payment", {})
        return gateway_order_id, {
            "order_id": str(order_id),
            "total_cents": total_cents,
            "payment": payment_payload,
            "payment_url": self._pakasir_client.build_payment_url(gateway_order_id, total_cents),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    async def mark_payment_completed(self, gateway_order_id: str, amount_cents: int) -> None:
        """Set payment and order status to completed."""
        pool = await get_pool()
        async with pool.acquire() as connection:
            async with connection.transaction():
                payment_row = await connection.fetchrow(
                    """
                    UPDATE payments
                    SET status = 'completed',
                        updated_at = NOW()
                    WHERE gateway_order_id = $1
                    RETURNING order_id;
                    """,
                    gateway_order_id,
                )
                if payment_row is None:
                    logger.warning("Payment not found for %s", gateway_order_id)
                    return

                order_id = payment_row["order_id"]
                await connection.execute(
                    """
                    UPDATE orders
                    SET status = 'paid',
                        updated_at = NOW()
                    WHERE id = $1;
                    """,
                    order_id,
                )
        await self._telemetry.increment("successful_transactions")

    async def mark_payment_failed(self, gateway_order_id: str) -> None:
        """Mark payment as failed/expired."""
        pool = await get_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """
                UPDATE payments
                SET status = 'failed',
                    updated_at = NOW()
                WHERE gateway_order_id = $1;
                """,
                gateway_order_id,
            )
        await self._telemetry.increment("failed_transactions")
