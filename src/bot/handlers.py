"""Telegram handlers wiring everything together."""

from __future__ import annotations

import logging
from typing import Any, Dict, Sequence

from telegram import CallbackQuery, Message, Update, User
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.bot.antispam import AntiSpamDecision, AntiSpamGuard
from src.bot import keyboards, messages
from src.core.config import get_settings
from src.core.currency import format_rupiah
from src.core.qr import qris_to_image
from src.core.telemetry import TelemetryTracker
from src.services.cart import Cart, CartManager
from src.services.catalog import Product, get_product, list_categories, list_products, list_products_by_category
from src.services.payment import PaymentError, PaymentService
from src.services.pakasir import PakasirClient
from src.services.stats import get_bot_statistics


logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command with welcome message and keyboards."""
    user = update.effective_user
    if user is None or update.message is None:
        return

    if await _check_spam(update, context):
        return

    settings = get_settings()
    stats = await get_bot_statistics()
    categories = await list_categories()
    products = await list_products()

    context.user_data["product_list"] = products

    mention = user.first_name or "Sahabat"
    welcome_text = messages.welcome_message(
        mention=mention,
        store_name=settings.store_name,
        total_users=stats["total_users"],
        total_transactions=stats["total_transactions"],
    )

    reply_keyboard = keyboards.main_reply_keyboard(range(1, min(len(products), 6)))

    await update.message.reply_text(
        welcome_text,
        reply_markup=reply_keyboard,
        parse_mode=ParseMode.MARKDOWN,
    )

    await update.message.reply_text(
        "🪄 Pilih kategori favoritmu ya!",
        reply_markup=keyboards.category_inline_keyboard(categories),
    )


def get_cart_manager(context: ContextTypes.DEFAULT_TYPE) -> CartManager:
    """Retrieve shared CartManager instance."""
    return context.application.bot_data["cart_manager"]  # type: ignore[return-value]


def get_payment_service(context: ContextTypes.DEFAULT_TYPE) -> PaymentService:
    """Retrieve PaymentService from bot_data."""
    return context.application.bot_data["payment_service"]  # type: ignore[return-value]


def get_telemetry(context: ContextTypes.DEFAULT_TYPE) -> TelemetryTracker:
    """Retrieve telemetry tracker from bot_data."""
    return context.application.bot_data["telemetry"]  # type: ignore[return-value]


def get_anti_spam(context: ContextTypes.DEFAULT_TYPE) -> AntiSpamGuard:
    """Retrieve anti-spam guard instance."""
    return context.application.bot_data["anti_spam"]  # type: ignore[return-value]


def _store_products(context: ContextTypes.DEFAULT_TYPE, products: Sequence[Product]) -> None:
    context.user_data["product_list"] = list(products)


async def handle_product_list(
    message: Message,
    context: ContextTypes.DEFAULT_TYPE,
    products: Sequence[Product],
    title: str,
) -> None:
    """Send formatted product list to user."""
    _store_products(context, products)
    header = messages.product_list_heading(title)
    lines = [
        messages.product_list_line(index, product)
        for index, product in enumerate(products, start=1)
    ]
    await message.reply_text(f"{header}\n" + "\n".join(lines[:10]))


def _parse_product_index(text: str) -> int | None:
    """Convert numeric keyboard text into zero-based index."""
    sanitized = text.replace("️⃣", "")
    sanitized = sanitized.strip()
    if sanitized.isdigit():
        return int(sanitized) - 1
    return None


async def show_product_detail(
    message: Message,
    context: ContextTypes.DEFAULT_TYPE,
    product: Product,
    cart: Cart,
) -> None:
    """Display product detail card with inline keyboard."""
    item = cart.items.get(product.id)
    quantity = item.quantity if item else 0
    await message.reply_text(
        messages.product_detail(product, quantity),
        reply_markup=keyboards.product_inline_keyboard(product, quantity),
    )


async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route reply keyboard text messages."""
    if update.message is None:
        return

    if await _check_spam(update, context):
        return

    text = (update.message.text or "").strip()

    if text in ("📋 List Produk", "📦 Semua Produk"):
        products = await list_products()
        await handle_product_list(update.message, context, products, "Semua Produk")
        return

    if text == "📊 Cek Stok":
        products = await list_products(limit=10)
        lines = [
            f"{product.name} • 📦 {product.stock}x • 🔥 {product.sold_count}x"
            for product in products
        ]
        await update.message.reply_text(
            "📦 Stok Teratas Saat Ini:\n" + "\n".join(lines[:10])
        )
        return

    if text == "💼 Deposit":
        await update.message.reply_text(
            "💼 Menu Deposit\n"
            "🧾 Kamu bisa transfer manual lalu kirim bukti ke admin, atau pilih metode otomatis QRIS di menu pembayaran.\n"
            "🤝 Saldo akan masuk setelah diverifikasi."
        )
        return

    index = _parse_product_index(text)
    if index is not None:
        products: Sequence[Product] = context.user_data.get("product_list", [])
        if 0 <= index < len(products):
            cart_manager = get_cart_manager(context)
            user_id = update.effective_user.id if update.effective_user else 0
            cart = await cart_manager.get_cart(user_id)
            await show_product_detail(update.message, context, products[index], cart)
        else:
            await update.message.reply_text("❓ Produk belum tersedia, coba pilih yang lain ya.")
        return

    await update.message.reply_text(messages.generic_error())


async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process callback data from inline keyboards."""
    query: CallbackQuery = update.callback_query  # type: ignore[assignment]
    if query is None:
        return
    data = query.data or ""
    user = update.effective_user
    if user is None:
        return

    if await _check_spam(update, context, alert_callback=True):
        return

    await query.answer()

    cart_manager = get_cart_manager(context)
    cart = await cart_manager.get_cart(user.id)

    if data.startswith("category:"):
        slug = data.split(":", maxsplit=1)[1]
        if slug == "all":
            products = await list_products()
            title = "Semua Produk"
        else:
            products = await list_products_by_category(slug)
            title = f"Produk {slug}"
        _store_products(context, products)
        await query.message.reply_text(
            f"{messages.product_list_heading(title)}\n"
            + "\n".join(
                messages.product_list_line(index, product)
                for index, product in enumerate(products, start=1)
            )
        )
        return

    if data.startswith("cart:"):
        parts = data.split(":")
        action = parts[1]
        if action in {"add", "remove", "set"}:
            product_id = int(parts[2])
            product = await get_product(product_id)
            if product is None:
                await query.message.reply_text("❌ Produk tidak ditemukan.")
                return
            if action == "add":
                cart.add(product, 1)
                await query.answer("🛒 Ditambahkan!")
            elif action == "remove":
                cart.remove(product_id, 1)
                await query.answer("➖ Dikurangi.")
            elif action == "set":
                target_qty = int(parts[3])
                cart.remove(product_id, 999)
                cart.add(product, target_qty)
                await query.answer(f"🧮 Diset {target_qty}x")
            item = cart.items.get(product.id)
            quantity = item.quantity if item else 0
            await query.message.edit_text(
                messages.product_detail(product, quantity),
                reply_markup=keyboards.product_inline_keyboard(product, quantity),
            )
            return

        if action == "checkout":
            total_items = cart.total_items()
            total_rp = format_rupiah(cart.total_cents())
            lines = cart.to_lines()
            await query.message.reply_text(
                messages.cart_summary(lines, total_items, total_rp),
                reply_markup=keyboards.cart_inline_keyboard(),
            )
            return

        if action in {"cancel", "clear"}:
            await cart_manager.clear_cart(user.id)
            await query.message.reply_text("🗑️ Keranjang sudah dikosongkan.")
            return

        if action == "coupon":
            await query.message.reply_text(
                "🎟️ Fitur kupon akan segera hadir. Nantikan ya!"
            )
            return

        if action == "pay":
            total_rp = format_rupiah(cart.total_cents())
            user_name = query.from_user.full_name
            balance_rp = format_rupiah(0)
            await query.message.reply_text(
                messages.payment_prompt(total_rp, user_name, balance_rp, "524107"),
                reply_markup=keyboards.payment_method_keyboard(),
            )
            return

    if data.startswith("pay:"):
        action = data.split(":", maxsplit=1)[1]
        payment_service = get_payment_service(context)
        telemetry = get_telemetry(context)
        cart = await cart_manager.get_cart(user.id)
        if action == "qris":
            try:
                await query.message.reply_text(messages.payment_loading())
                gateway_order_id, payload = await payment_service.create_invoice(
                    telegram_user={
                        "id": user.id,
                        "username": user.username,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                    },
                    cart=cart,
                    method="qris",
                )
            except PaymentError as exc:
                await telemetry.increment("failed_transactions")
                await query.message.reply_text(f"⚠️ {exc}")
                return

            payment_data = payload["payment"]
            invoice_text = messages.payment_invoice_detail(
                invoice_id=gateway_order_id,
                items=cart.to_lines(),
                total_rp=format_rupiah(cart.total_cents()),
                expires_in="5 Menit",
                created_at=payload["created_at"],
            )
            qr_data = str(payment_data.get("payment_number", ""))
            if qr_data:
                await query.message.reply_photo(
                    photo=qris_to_image(qr_data),
                    caption=invoice_text,
                    reply_markup=keyboards.invoice_keyboard(payload["payment_url"]),
                )
            else:
                await query.message.reply_text(
                    invoice_text + "\n\n(⚠️ QR tidak tersedia, gunakan tautan checkout.)",
                    reply_markup=keyboards.invoice_keyboard(payload["payment_url"]),
                )
            return
        if action == "balance":
            await query.message.reply_text(
                "💼 Saldo belum tersedia. Coba pakai QRIS dulu ya!"
            )
            return
        if action == "cancel":
            await cart_manager.clear_cart(user.id)
            await query.message.reply_text(messages.payment_expired("DIBATALKAN"))
            return


def register(application: Application) -> None:
    """Register command, callback, and text handlers."""
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(callback_router))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, text_router)
    )


def setup_bot_data(application: Application, pakasir_client: PakasirClient, telemetry: TelemetryTracker) -> None:
    """Populate application.bot_data with shared services."""
    application.bot_data["cart_manager"] = CartManager()
    application.bot_data["telemetry"] = telemetry
    application.bot_data["pakasir_client"] = pakasir_client
    application.bot_data["payment_service"] = PaymentService(
        pakasir_client=pakasir_client,
        telemetry=telemetry,
    )
    application.bot_data["anti_spam"] = AntiSpamGuard()


async def _check_spam(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    alert_callback: bool = False,
) -> bool:
    user = update.effective_user
    if user is None:
        return False
    anti_spam = get_anti_spam(context)
    decision = await anti_spam.register_action(user.id)
    if decision.allowed:
        return False

    await _handle_spam(decision, update, context, user, alert_callback=alert_callback)
    return True


async def _handle_spam(
    decision: AntiSpamDecision,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User,
    *,
    alert_callback: bool,
) -> None:
    logger.warning("Spam detected from user_id=%s", user.id)
    warning_text = "🚫 Jangan spam ya, tindakanmu akan dilaporkan ke admin."

    if alert_callback and update.callback_query:
        try:
            await update.callback_query.answer("⛔️ Stop spamming!", show_alert=True)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Failed to answer callback for spam alert: %s", exc)

    if decision.warn_user:
        target_message = update.effective_message
        try:
            if target_message is not None:
                await target_message.reply_text(warning_text)
            else:
                await context.bot.send_message(chat_id=user.id, text=warning_text)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Failed to send spam warning to user %s: %s", user.id, exc)

    if decision.notify_admin:
        settings = get_settings()
        if not settings.telegram_admin_ids:
            return
        alert = (
            "🚨 Deteksi spam pada bot!\n"
            f"• Nama: {user.full_name}\n"
            f"• Username: @{user.username or 'tanpa_username'}\n"
            f"• Telegram ID: {user.id}"
        )
        for admin_id in settings.telegram_admin_ids:
            try:
                await context.bot.send_message(chat_id=admin_id, text=alert)
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug("Failed to notify admin %s: %s", admin_id, exc)
