"""Telegram handlers wiring everything together."""

from __future__ import annotations

import asyncio
import html
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

from telegram import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
    User,
)
from telegram.constants import ParseMode
from telegram.error import Forbidden, TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    ConversationHandler,
    filters,
)

from src.bot.antispam import AntiSpamDecision, AntiSpamGuard
from src.bot import keyboards, messages
from src.core.config import get_settings
from src.core.currency import format_rupiah
from src.core.qr import qris_to_image
from src.core.custom_config import (
    CustomConfigManager,
    PostgresConfigAdapter,
    DummyDBAdapter,
)
from src.bot.admin.admin_menu import handle_admin_menu
from src.bot.admin.admin_actions import (
    AdminActionError,
    handle_block_user_input,
    handle_update_order_input,
    handle_generate_voucher_input,
    handle_delete_voucher_input,
    render_order_overview,
    render_product_overview,
    render_user_overview,
    render_voucher_overview,
    save_product_snk,
    parse_price_to_cents,
)
from src.bot.admin.admin_state import (
    clear_admin_state,
    get_admin_state,
    set_admin_state,
)
from src.core.telemetry import TelemetryTracker
from src.services.cart import Cart, CartManager
from src.services.catalog import (
    Product,
    add_product,
    delete_product,
    edit_product,
    get_product,
    list_categories,
    list_products,
    list_products_by_category,
)
from src.services.locks import LockNotAcquired, distributed_lock
from src.services.payment import PaymentError, PaymentService
from src.services.pakasir import PakasirClient
from src.services.stats import get_bot_statistics
from src.services.calculator import (
    load_config,
    calculate_refund,
    add_history,
    get_history,
    update_config,
)
from src.services.users import (
    get_user_profile,
    is_user_blocked,
    list_broadcast_targets,
    list_users,
    mark_user_bot_blocked,
    update_user_profile,
)
from src.services.order import get_last_order_for_user, list_order_items
from src.services.broadcast_queue import (
    create_job as create_broadcast_job,
    fetch_pending_targets,
    mark_target_success,
    mark_target_failed,
    finalize_jobs,
    get_job_summary,
)
from src.services.terms import (
    clear_product_terms,
    get_notification,
    list_pending_notifications,
    mark_notification_responded,
    mark_notification_sent,
    record_terms_submission,
    purge_old_submissions,
)
from src.services.payment_messages import (
    record_payment_message,
    delete_payment_messages,
)


logger = logging.getLogger(__name__)

DEFAULT_BANK_ID = "524107"
CARA_ORDER_TEXT_KEY = "template.cara_order.text"
CARA_ORDER_PHOTO_KEY = "template.cara_order.photo_id"
DEFAULT_CARA_ORDER_TEXT = (
    "📘 <b>Cara Order</b>\n\n"
    "1. Pilih produk dari katalog atau ketik angka sesuai produk favorit kamu.\n"
    "2. Tekan tombol <b>Tambahkan ke Keranjang</b> untuk memasukkan produk ke keranjang.\n"
    "3. Lanjutkan ke pembayaran dan selesaikan transaksi sebelum waktu habis.\n"
    "4. Setelah pembayaran sukses, detail produk otomatis dikirim ke chat kamu.\n\n"
    "Butuh bantuan? Hubungi admin melalui menu INFORMASI."
)


class _TemplateSafeDict(dict):
    """Fallback dict that keeps unknown placeholders intact."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _apply_template(text: str, **kwargs: Any) -> str:
    """Render template safely, leaving unknown placeholders untouched."""
    try:
        return text.format_map(_TemplateSafeDict(**kwargs))
    except Exception:
        return text


def _get_config_manager(
    context: ContextTypes.DEFAULT_TYPE,
) -> Optional[CustomConfigManager]:
    manager = context.application.bot_data.get("custom_config_mgr")
    return manager if isinstance(manager, CustomConfigManager) else None


async def _get_cara_order_template(
    context: ContextTypes.DEFAULT_TYPE,
) -> Tuple[str, Optional[str]]:
    manager = _get_config_manager(context)
    if not manager:
        return DEFAULT_CARA_ORDER_TEXT, None

    text = await manager.get_config(CARA_ORDER_TEXT_KEY) or DEFAULT_CARA_ORDER_TEXT
    photo_id = await manager.get_config(CARA_ORDER_PHOTO_KEY) or None
    if photo_id == "":
        photo_id = None
    return text, photo_id


async def _save_cara_order_template(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    text: str,
    actor_id: int,
    photo_file_id: Optional[str] = None,
) -> None:
    manager = _get_config_manager(context)
    if not manager:
        return
    await manager.set_config(CARA_ORDER_TEXT_KEY, text, actor_id=actor_id)
    await manager.db.set_config(
        CARA_ORDER_PHOTO_KEY, photo_file_id or "", updated_by=actor_id
    )


def _extract_display_name(
    profile: Optional[Dict[str, Any]], user: Optional[User]
) -> str:
    if profile:
        display_name = profile.get("display_name")
        if display_name:
            return str(display_name)
    if user and user.first_name:
        return user.first_name
    if user and user.username:
        return user.username
    return "Customer"


def _build_user_info_message(
    profile: Optional[Dict[str, Any]],
    *,
    user: Optional[User],
) -> str:
    telegram_id = profile.get("telegram_id") if profile else (user.id if user else None)
    balance_cents = int(profile.get("balance_cents") or 0) if profile else 0
    bank_id = profile.get("bank_id") if profile else None
    verified = bool(profile.get("is_verified")) if profile else False
    balance_text = format_rupiah(balance_cents)
    display_name = _extract_display_name(profile, user)
    verified_text = str(verified).lower()
    bank_text = bank_id or DEFAULT_BANK_ID
    telegram_display = telegram_id if telegram_id is not None else "-"
    return (
        "ℹ️ <b>Informasi Akun Kamu</b>\n\n"
        f"ᯓ Nama: {html.escape(display_name)}\n"
        f"ᯓ Saldo: {balance_text}\n"
        f"ᯓ Bank ID: {bank_text}\n"
        f"ᯓ Terverifikasi: {verified_text}\n"
        f"ᯓ User ID: {telegram_display}"
    )


def _build_profile_settings_message(
    profile: Optional[Dict[str, Any]], user: Optional[User]
) -> str:
    display_name = _extract_display_name(profile, user)
    username_value = profile.get("display_name") if profile else None
    whatsapp_value = profile.get("whatsapp_number") if profile else None
    username_text = username_value or "Anonymous"
    whatsapp_text = whatsapp_value or "null"
    return (
        f"Halo <b>{html.escape(display_name)}</b>, Ini adalah beberapa konfigurasi dari data kamu 👋🏻\n\n"
        "<b>Detail User</b>\n\n"
        f"- <b>Username:</b> {html.escape(username_text)}\n"
        f"- <b>No Whatsapp:</b> {html.escape(whatsapp_text)}\n\n"
        "Disini anda bisa mengatur beberapa pengaturan bot, klik tombol di bawah untuk mengatur pengaturan bot."
    )


def _build_customer_service_message(settings) -> str:
    admin_ids = list(settings.telegram_admin_ids or [])
    owner_ids = list(settings.telegram_owner_ids or [])
    if not admin_ids:
        admin_ids = owner_ids
    if not admin_ids:
        return (
            "👨‍💼 <b>Customer Service</b>\n\n"
            "Belum ada kontak admin yang terdaftar. Silakan hubungi owner bot secara langsung."
        )
    lines = ["👨‍💼 <b>Customer Service</b>\n"]
    for idx, admin_id in enumerate(admin_ids, start=1):
        lines.append(f'• <a href="tg://user?id={admin_id}">Hubungi Admin {idx}</a>')
    lines.append(
        "\nTim admin siap membantu kamu menyelesaikan transaksi atau memverifikasi pembayaran manual."
    )
    return "\n".join(lines)


def _build_stock_overview_message(
    products: Sequence[Product],
    *,
    tz_name: str,
) -> str:
    now_utc = datetime.now(timezone.utc)
    try:
        local_dt = now_utc.astimezone(ZoneInfo(tz_name))
    except Exception:
        local_dt = now_utc
    timestamp = f"{local_dt.month}/{local_dt.day}/{local_dt.year}, {local_dt.strftime('%I:%M:%S %p')}"
    lines = []
    for idx, product in enumerate(products, start=1):
        lines.append(f"<b>— {idx}. {html.escape(product.name)} ➜ {product.stock}x</b>")
    body = "\n".join(lines) if lines else "<i>Belum ada produk.</i>"
    return (
        "📦 <b>Informasi Stok</b>\n"
        f"- Tanggal: {timestamp}\n\n"
        f"{body}\n\n"
        "Untuk membeli produk ketik angka yang ingin kamu beli."
    )


async def _build_last_transaction_message(
    telegram_id: int,
    *,
    settings,
) -> str:
    order = await get_last_order_for_user(telegram_id)
    if not order:
        return (
            "🧾 <b>Transaksi Terakhir</b>\n\n"
            "Belum ada transaksi tercatat. Yuk mulai belanja!"
        )
    order_id = int(order["id"])
    order_id_str = str(order_id)
    total_cents = int(order.get("total_price_cents") or 0)
    total_text = format_rupiah(total_cents)
    status = str(order.get("status") or "-").upper()
    payment_status = str(order.get("payment_status") or "-").upper()
    gateway_order_id = order.get("gateway_order_id") or "-"
    created_at = order.get("created_at")
    try:
        tz = ZoneInfo(settings.bot_timezone)
    except Exception:
        tz = timezone.utc
    if isinstance(created_at, datetime):
        created_local = created_at.astimezone(tz)
    else:
        created_local = datetime.now(tz)
    timestamp = created_local.strftime("%d/%m/%Y %H:%M")
    items = await list_order_items(order_id)
    item_lines = []
    for idx, item in enumerate(items, start=1):
        product_name = html.escape(item.get("product_name") or f"Produk {idx}")
        quantity = int(item.get("quantity") or 0)
        unit_price_cents = int(item.get("unit_price_cents") or 0)
        line_total = format_rupiah(unit_price_cents * quantity)
        item_lines.append(f"{idx}. {product_name} x{quantity} = {line_total}")
    items_block = "\n".join(item_lines) if item_lines else "-"
    return (
        "🧾 <b>Transaksi Terakhir</b>\n\n"
        f"<b>Order ID:</b> <code>{order_id_str}</code>\n"
        f"<b>Gateway ID:</b> <code>{gateway_order_id}</code>\n"
        f"<b>Status Order:</b> {status}\n"
        f"<b>Status Pembayaran:</b> {payment_status}\n"
        f"<b>Total:</b> {total_text}\n"
        f"<b>Tanggal:</b> {timestamp}\n\n"
        "<b>Produk:</b>\n"
        f"{items_block}"
    )


async def _send_welcome_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User,
    message: Message | None = None,
) -> None:
    """Send welcome message with inline keyboard for quick actions."""
    settings = get_settings()
    stats = await get_bot_statistics()
    products = await list_products()

    context.user_data["product_list"] = products

    mention = user.first_name or "Sahabat"
    welcome_text = messages.welcome_message(
        mention=mention,
        store_name=settings.store_name,
        total_users=stats["total_users"],
        total_transactions=stats["total_transactions"],
    )

    # Check if user is admin
    is_admin = (
        user.id in settings.telegram_admin_ids or user.id in settings.telegram_owner_ids
    )

    # Use admin keyboard for admins, regular keyboard for customers
    from src.bot.admin.admin_menu import admin_main_menu

    target_message = message or update.message
    if target_message is None:
        return

    if is_admin:
        reply_keyboard = admin_main_menu()
    else:
        reply_keyboard = keyboards.main_reply_keyboard(range(1, min(len(products), 6)))

    # Send welcome message with reply keyboard (no extra messages)
    await target_message.reply_text(
        welcome_text,
        reply_markup=keyboards.welcome_inline_keyboard(),
        parse_mode=ParseMode.HTML,
    )

    await target_message.reply_text(
        "⌨️ Menu utama tersedia di keyboard bawah. Pilih angka atau menu yang kamu butuhkan ya!",
        reply_markup=reply_keyboard,
        parse_mode=ParseMode.HTML,
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command with welcome message and keyboards."""
    user = update.effective_user
    if user is None or update.message is None:
        return

    if await _check_spam(update, context):
        return

    # Upsert user to ensure they're counted in statistics
    from src.services.users import upsert_user

    await upsert_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )

    # Send sticker first
    await update.message.reply_sticker(
        sticker="CAACAgIAAxkBAAIDbWkLZHuqPRCqCqmL9flozT9YJdWOAAIZUAAC4KOCB7lIn3OKexieNgQ"
    )

    await _send_welcome_message(update, context, user)


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


def _store_products(
    context: ContextTypes.DEFAULT_TYPE, products: Sequence[Product]
) -> None:
    context.user_data["product_list"] = list(products)


async def handle_product_list(
    message: Message,
    context: ContextTypes.DEFAULT_TYPE,
    products: Sequence[Product],
    title: str,
    page: int = 0,
) -> None:
    """Send formatted product list to user with pagination."""
    try:
        _store_products(context, products)

        if not products:
            await message.reply_text(
                "📦 <b>Belum Ada Produk</b>\n\n"
                "Saat ini belum ada produk yang tersedia.\n"
                "Silakan cek lagi nanti ya! 😊",
                parse_mode=ParseMode.HTML,
            )
            return

        header = messages.product_list_heading(title)
        lines = [
            messages.product_list_line(index, product)
            for index, product in enumerate(products, start=1)
        ]

        # Pagination: 5 products per page
        items_per_page = 5
        total_pages = (len(products) + items_per_page - 1) // items_per_page
        page = max(0, min(page, total_pages - 1))

        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        page_lines = lines[start_idx:end_idx]

        text = f"{header}\n" + "\n".join(page_lines)
        text += f"\n\n📄 <b>Halaman {page + 1}/{total_pages}</b>"

        # Build pagination buttons
        buttons = []
        nav_row = []
        if page > 0:
            nav_row.append(
                InlineKeyboardButton(
                    "⬅️ Previous", callback_data=f"products:page:{page - 1}"
                )
            )
        if page < total_pages - 1:
            nav_row.append(
                InlineKeyboardButton(
                    "➡️ Next", callback_data=f"products:page:{page + 1}"
                )
            )

        if nav_row:
            buttons.append(nav_row)

        # Add product selection buttons (first 5 products on current page)
        for idx, product in enumerate(products[start_idx:end_idx], start=start_idx + 1):
            buttons.append(
                [
                    InlineKeyboardButton(
                        f"{idx}",
                        callback_data=f"product:{product.id}",
                    )
                ]
            )

        keyboard = InlineKeyboardMarkup(buttons) if buttons else None

        await message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    except Exception as exc:
        logger.exception("Error displaying product list: %s", exc)
        await message.reply_text(
            "❌ <b>Gagal menampilkan produk</b>\n\n"
            "Terjadi kesalahan saat memuat daftar produk.\n"
            "Silakan coba lagi atau hubungi admin.",
            parse_mode=ParseMode.HTML,
        )


def _parse_product_index(text: str) -> int | None:
    """Convert numeric keyboard text into zero-based index."""
    sanitized = text.replace("️⃣", "")
    sanitized = sanitized.strip()
    if sanitized.isdigit():
        return int(sanitized) - 1
    return None


async def _handle_add_product_snk_choice(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    state: Any,
    text: str,
) -> None:
    """Process admin choice to add or skip SNK after product creation."""
    choice = text.strip().lower()
    payload = state.payload or {}
    if choice == "tambah snk":
        context.user_data.pop("pending_snk_product", None)
        set_admin_state(context.user_data, "add_product_snk_input", **payload)
        await update.message.reply_text(
            "Silakan kirim SNK untuk produk ini. Kamu bisa tulis beberapa baris "
            "untuk menjelaskan aturan, langkah login, dan batas waktu klaim.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    if choice == "skip snk":
        context.user_data.pop("pending_snk_product", None)
        clear_admin_state(context.user_data)
        await update.message.reply_text(
            "👍 Baik, SNK tidak ditambahkan. Kamu bisa mengelolanya lagi dari menu 📜 Kelola SNK Produk.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    await update.message.reply_text(
        "Silakan pilih tombol 'Tambah SNK' atau 'Skip SNK' ya."
    )


def _limit_words(value: str, max_words: int = 3) -> str:
    """Return string limited to given number of words."""
    if not value:
        return "-"
    words = value.split()
    return " ".join(words[:max_words]) if words else "-"


def _format_html_lines(value: str | None) -> str:
    """Escape text for HTML and preserve newlines with <br>."""
    if not value:
        return "-"
    return "<br>".join(html.escape(part) for part in value.splitlines())


def _get_seller_recipient_ids(
    context: ContextTypes.DEFAULT_TYPE,
) -> list[int]:
    """Return admin IDs excluding owner IDs."""
    admin_ids = context.application.bot_data.get("admin_ids", [])
    owner_ids = set(context.application.bot_data.get("owner_ids", []))
    recipients: list[int] = []
    for raw_id in admin_ids:
        if raw_id in owner_ids:
            continue
        try:
            recipients.append(int(raw_id))
        except (TypeError, ValueError):
            logger.warning("Admin ID %s tidak valid untuk notifikasi.", raw_id)
    return recipients


async def _notify_admin_new_order(
    context: ContextTypes.DEFAULT_TYPE,
    user: User,
    cart: Cart,
    *,
    order_id: str,
    method: str,
    created_at: str,
    gateway_order_id: str,
) -> None:
    """Send new order notification to seller/admins."""
    recipients = _get_seller_recipient_ids(context)
    if not recipients:
        return
    settings = get_settings()
    try:
        created_dt = datetime.fromisoformat(created_at)
    except (ValueError, TypeError):
        created_dt = datetime.now(timezone.utc)
    try:
        tz = ZoneInfo(settings.bot_timezone)
    except Exception:  # pragma: no cover - fallback path
        tz = timezone.utc
    created_local = created_dt.astimezone(tz)
    timestamp_str = created_local.strftime("%d-%m-%Y %H:%M")
    name_source = user.full_name or user.username or "Customer"
    customer_name = _limit_words(name_source)
    username = f"@{user.username}" if user.username else "-"
    products = [f"{item.quantity}x {item.product.name}" for item in cart.items.values()]
    products_text = ", ".join(products) if products else "-"
    method_label = "Deposit" if method == "deposit" else "Otomatis"
    if method not in {"deposit", ""}:
        method_label += f" ({method.upper()})"
    message_text = (
        f"🛒 <b>Pesanan Baru dari {html.escape(customer_name)}</b>\n\n"
        f"<b>ID Telegram:</b> {user.id}\n"
        f"<b>Username:</b> {html.escape(username)}\n"
        f"<b>Pesanan:</b> {html.escape(products_text)}\n"
        f"<b>Metode Pembayaran:</b> {html.escape(method_label)}\n"
        f"<b>ID Pesanan:</b> {html.escape(order_id)}\n"
        f"<b>Tanggal Pembelian:</b> {html.escape(timestamp_str)}\n\n"
        "✨ <b>Silakan simpan catatan pesanan ini jika perlu. Terima kasih</b> ✨"
    )
    for admin_id in recipients:
        try:
            sent_message = await context.bot.send_message(
                chat_id=admin_id,
                text=message_text,
                parse_mode=ParseMode.HTML,
            )
            await record_payment_message(
                gateway_order_id=gateway_order_id,
                chat_id=sent_message.chat_id,
                message_id=sent_message.message_id,
                role="admin_order_alert",
                message_kind="text",
            )
        except TelegramError as exc:  # pragma: no cover - network failure
            logger.warning(
                "[notif] Gagal mengirim notifikasi order ke admin %s: %s",
                admin_id,
                exc,
            )


async def _notify_admin_snk_submission(
    context: ContextTypes.DEFAULT_TYPE,
    notification: Dict[str, Any],
    user: User,
    message_text: str | None,
    *,
    media_file_id: str | None,
    media_type: str | None,
) -> None:
    """Forward SNK submission to admins (without owner)."""
    recipients = _get_seller_recipient_ids(context)
    if not recipients:
        return
    product = await get_product(int(notification["product_id"]))
    product_name = product.name if product else "-"
    customer_name = _limit_words(user.full_name or user.username or "Customer")
    order_id = str(notification["order_id"])
    submission_text = _format_html_lines(message_text)
    body = (
        f"<b>PESAN BARU DARI {html.escape(customer_name)}</b><br><br>"
        f"<b>INFORMASI</b>: 'Penuhi SNK'<br>"
        f"{submission_text}<br><br>"
        f"<b>Produk:</b> {html.escape(product_name)}<br>"
        f"<b>Order ID:</b> {html.escape(order_id)}"
    )
    for admin_id in recipients:
        try:
            if media_file_id and media_type == "photo":
                await context.bot.send_photo(
                    chat_id=admin_id,
                    photo=media_file_id,
                    caption=body,
                    parse_mode=ParseMode.HTML,
                )
            else:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=body,
                    parse_mode=ParseMode.HTML,
                )
        except TelegramError as exc:  # pragma: no cover - network failure
            logger.warning("[snk] Gagal meneruskan SNK ke admin %s: %s", admin_id, exc)


async def _handle_snk_submission_message(
    message: Message,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    text: str | None,
    media_file_id: str | None,
    media_type: str | None,
) -> bool:
    """Persist SNK submission when user sends text or media."""
    snk_state = context.user_data.get("snk_submission")
    if not snk_state:
        return False
    notification_id = int(snk_state.get("notification_id") or 0)
    if notification_id <= 0:
        context.user_data.pop("snk_submission", None)
        await message.reply_text(
            "⚠️ Permintaan SNK tidak valid. Silakan klik tombol 'Penuhi SNK' lagi."
        )
        return True
    notification = await get_notification(notification_id)
    if notification is None:
        context.user_data.pop("snk_submission", None)
        await message.reply_text(
            "⚠️ Permintaan SNK sudah tidak berlaku. Tekan tombol SNK lagi ya."
        )
        return True
    user = message.from_user
    if user is None or int(notification["telegram_user_id"]) != user.id:
        context.user_data.pop("snk_submission", None)
        await message.reply_text("❌ Permintaan SNK tidak cocok dengan akun kamu.")
        return True
    submission_text = text or ""
    if not submission_text and not media_file_id:
        await message.reply_text("📸 Kirim screenshot atau pesan keterangannya ya.")
        return True
    await record_terms_submission(
        order_id=str(notification["order_id"]),
        product_id=int(notification["product_id"]),
        telegram_user_id=user.id,
        message=submission_text or None,
        media_file_id=media_file_id,
        media_type=media_type,
    )
    await mark_notification_responded(notification_id)
    context.user_data.pop("snk_submission", None)
    await message.reply_text(
        "✅ Terima kasih! Kami sudah terima bukti SNK kamu. Admin akan meninjau secepatnya."
    )
    await _notify_admin_snk_submission(
        context,
        notification,
        user,
        submission_text or "-",
        media_file_id=media_file_id,
        media_type=media_type,
    )
    return True


def _format_broadcast_summary(job_id: int, counts: Dict[str, int]) -> str:
    """Bangun ringkasan status broadcast."""
    total = sum(counts.values())
    sent = counts.get("sent", 0)
    failed = counts.get("failed", 0)
    pending = counts.get("pending", 0)
    return (
        "📣 Broadcast dijadwalkan!\n"
        f"🆔 Job: #{job_id}\n"
        f"👥 Target: {total}\n"
        f"✅ Terkirim: {sent}\n"
        f"⚠️ Pending: {pending}\n"
        f"🚫 Gagal: {failed}\n"
        "Progress dipantau otomatis, cek log audit untuk detail."
    )


async def _schedule_broadcast_job(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    actor_id: int,
    text: str | None,
    media_file_id: str | None = None,
    media_type: str | None = None,
) -> Dict[str, int | str]:
    """Enqueue broadcast dan mulai dispatcher."""

    targets = await list_broadcast_targets()
    valid_targets = [
        int(row["telegram_id"]) for row in targets if row.get("telegram_id") is not None
    ]
    if not valid_targets:
        logger.info("[broadcast] Tidak ada target broadcast.")
        return {"message": "📣 Tidak ada user yang bisa menerima broadcast saat ini."}

    job_id = await create_broadcast_job(
        actor_telegram_id=actor_id,
        message=text,
        media_file_id=media_file_id,
        media_type=media_type,
        targets=valid_targets,
    )
    summary = await get_job_summary(job_id)
    # Trigger dispatcher segera agar job mulai berjalan
    await process_broadcast_queue(context)
    return {
        "job_id": job_id,
        "counts": summary.get("counts", {}),
    }


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
        parse_mode=ParseMode.HTML,
    )


async def process_pending_snk_notifications(
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Background job to deliver SNK messages to customers."""
    try:
        async with distributed_lock("snk_notification_dispatch"):
            notifications = await list_pending_notifications(limit=10)
            if not notifications:
                return
            for notification in notifications:
                notification_id = int(notification["id"])
                telegram_user_id = int(notification["telegram_user_id"])
                product_id = int(notification["product_id"])
                product = await get_product(product_id)
                product_name = product.name if product else "produk ini"
                snk_text = notification.get("content") or ""
                message_text = (
                    f"📜 SNK untuk {product_name}\n\n"
                    f"{snk_text}\n\n"
                    "Jika sudah mengikuti instruksi, klik tombol di bawah untuk kirim bukti ya."
                )
                try:
                    await context.bot.send_message(
                        chat_id=telegram_user_id,
                        text=message_text,
                        reply_markup=keyboards.snk_confirmation_keyboard(
                            notification_id
                        ),
                    )
                    await mark_notification_sent(notification_id)
                except Forbidden:
                    logger.warning(
                        "[snk] User %s memblokir bot saat kirim SNK.",
                        telegram_user_id,
                    )
                    await mark_notification_sent(notification_id)
                    await mark_user_bot_blocked(telegram_user_id)
                except TelegramError as exc:  # pragma: no cover - network failure
                    logger.error(
                        "[snk] Gagal mengirim SNK ke user %s: %s",
                        telegram_user_id,
                        exc,
                    )
                await asyncio.sleep(0.05)
    except LockNotAcquired:
        logger.debug(
            "[snk] Pengiriman SNK dilewati karena lock dipegang instance lain."
        )


async def process_broadcast_queue(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Dispatcher untuk antrian broadcast yang persisten di database."""

    targets = await fetch_pending_targets(limit=20)
    if not targets:
        await finalize_jobs()
        return

    for target in targets:
        target_id = int(target["id"])
        telegram_id = int(target["telegram_id"])
        message_text = target.get("message") or ""
        media_file_id = target.get("media_file_id")
        media_type = target.get("media_type")
        try:
            if media_file_id and media_type == "photo":
                await context.bot.send_photo(
                    chat_id=telegram_id,
                    photo=media_file_id,
                    caption=message_text,
                )
            else:
                await context.bot.send_message(chat_id=telegram_id, text=message_text)
            await mark_target_success(target_id)
        except Forbidden:
            await mark_target_failed(target_id, "bot diblokir")
            await mark_user_bot_blocked(telegram_id)
            logger.warning(
                "[broadcast] User %s memblokir bot, target ditandai gagal.",
                telegram_id,
            )
        except TelegramError as exc:  # pragma: no cover - network failure
            await mark_target_failed(target_id, str(exc))
            logger.error(
                "[broadcast] Gagal mengirim ke %s: %s",
                telegram_id,
                exc,
            )
        await asyncio.sleep(0.05)

    await finalize_jobs()


async def purge_snk_submissions_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Hapus submission SNK lama sesuai retention policy."""

    settings = get_settings()
    retention = getattr(settings, "snk_retention_days", 30)
    if retention <= 0:
        return
    deleted = await purge_old_submissions(retention)
    if deleted:
        logger.info("[snk] Purge %s submission lama (>%s hari).", deleted, retention)


async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route reply keyboard text messages."""
    if update.message is None:
        return

    if await _check_spam(update, context):
        return

    text = (update.message.text or "").strip()
    if await _handle_snk_submission_message(
        update.message,
        context,
        text=text,
        media_file_id=None,
        media_type=None,
    ):
        return
    admin_ids = context.bot_data.get("admin_ids", [])
    user = update.effective_user
    user_id_str = str(user.id) if user else ""
    is_admin = user_id_str in admin_ids

    profile_state = context.user_data.get("profile_edit")
    if profile_state:
        field = profile_state.get("field")
        if text.lower() == "batal":
            context.user_data.pop("profile_edit", None)
            await update.message.reply_text(
                "✅ Pengaturan dibatalkan.",
                parse_mode=ParseMode.HTML,
            )
            return
        if user is None:
            context.user_data.pop("profile_edit", None)
            await update.message.reply_text(
                "⚠️ Tidak dapat memperbarui profil tanpa informasi user.",
                parse_mode=ParseMode.HTML,
            )
            return
        if field == "display_name":
            candidate = text.strip()
            if not (3 <= len(candidate) <= 32):
                await update.message.reply_text(
                    "⚠️ Username harus 3-32 karakter.",
                    parse_mode=ParseMode.HTML,
                )
                return
            await update_user_profile(user.id, display_name=candidate)
            context.user_data.pop("profile_edit", None)
            await update.message.reply_text(
                "✅ Username berhasil diperbarui.",
                parse_mode=ParseMode.HTML,
            )
            profile = await get_user_profile(user.id)
            await update.message.reply_text(
                _build_profile_settings_message(profile, user),
                reply_markup=keyboards.info_settings_keyboard(),
                parse_mode=ParseMode.HTML,
            )
            return
        if field == "whatsapp":
            digits = "".join(ch for ch in text if ch.isdigit())
            if not (9 <= len(digits) <= 15):
                await update.message.reply_text(
                    "⚠️ Nomor WhatsApp harus terdiri dari 9-15 digit.",
                    parse_mode=ParseMode.HTML,
                )
                return
            await update_user_profile(user.id, whatsapp_number=digits)
            context.user_data.pop("profile_edit", None)
            await update.message.reply_text(
                "✅ Nomor WhatsApp berhasil diperbarui.",
                parse_mode=ParseMode.HTML,
            )
            profile = await get_user_profile(user.id)
            await update.message.reply_text(
                _build_profile_settings_message(profile, user),
                reply_markup=keyboards.info_settings_keyboard(),
                parse_mode=ParseMode.HTML,
            )
            return

    if is_admin:
        state = get_admin_state(context.user_data)
        if state:
            reply_kwargs: Dict[str, Any] = {}
            keep_state = False
            try:
                if state.action == "add_product_step":
                    # Handle step-by-step wizard for adding product
                    step = state.payload.get("step", "code")
                    product_data = state.payload.get("product_data", {})

                    cancel_keyboard = InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "❌ Batal", callback_data="admin:cancel"
                                )
                            ]
                        ]
                    )

                    if step == "code":
                        # Save code and ask for name
                        product_data["code"] = text.strip()
                        set_admin_state(
                            context.user_data,
                            "add_product_step",
                            step="name",
                            product_data=product_data,
                        )
                        await update.message.reply_text(
                            "➕ <b>Tambah Produk Baru</b>\n\n"
                            "Langkah 2/5: Kirim <b>nama produk</b> (contoh: Netflix Premium 1 Bulan)\n\n"
                            f"✅ Kode: <code>{product_data['code']}</code>",
                            reply_markup=cancel_keyboard,
                            parse_mode=ParseMode.HTML,
                        )
                        return
                    elif step == "name":
                        # Save name and ask for price
                        product_data["name"] = text.strip()
                        set_admin_state(
                            context.user_data,
                            "add_product_step",
                            step="price",
                            product_data=product_data,
                        )
                        await update.message.reply_text(
                            "➕ <b>Tambah Produk Baru</b>\n\n"
                            "Langkah 3/5: Kirim <b>harga produk</b> (contoh: 50000)\n\n"
                            f"✅ Kode: <code>{product_data['code']}</code>\n"
                            f"✅ Nama: <b>{product_data['name']}</b>",
                            reply_markup=cancel_keyboard,
                            parse_mode=ParseMode.HTML,
                        )
                        return
                    elif step == "price":
                        # Save price and ask for stock
                        try:
                            price_cents = parse_price_to_cents(text.strip())
                            product_data["price_cents"] = price_cents
                        except AdminActionError as exc:
                            await update.message.reply_text(
                                f"❌ {exc}\n\nSilakan kirim harga yang valid (contoh: 50000)",
                                reply_markup=cancel_keyboard,
                                parse_mode=ParseMode.HTML,
                            )
                            return
                        set_admin_state(
                            context.user_data,
                            "add_product_step",
                            step="stock",
                            product_data=product_data,
                        )
                        await update.message.reply_text(
                            "➕ <b>Tambah Produk Baru</b>\n\n"
                            "Langkah 4/5: Kirim <b>jumlah stok</b> (contoh: 100)\n\n"
                            f"✅ Kode: <code>{product_data['code']}</code>\n"
                            f"✅ Nama: <b>{product_data['name']}</b>\n"
                            f"✅ Harga: <b>{format_rupiah(product_data['price_cents'])}</b>",
                            reply_markup=cancel_keyboard,
                            parse_mode=ParseMode.HTML,
                        )
                        return
                    elif step == "stock":
                        # Save stock and ask for description
                        try:
                            stock = int(text.strip())
                            product_data["stock"] = stock
                        except ValueError:
                            await update.message.reply_text(
                                "❌ Stok harus berupa angka.\n\nSilakan kirim stok yang valid (contoh: 100)",
                                reply_markup=cancel_keyboard,
                                parse_mode=ParseMode.HTML,
                            )
                            return
                        set_admin_state(
                            context.user_data,
                            "add_product_step",
                            step="description",
                            product_data=product_data,
                        )
                        await update.message.reply_text(
                            "➕ <b>Tambah Produk Baru</b>\n\n"
                            "Langkah 5/5: Kirim <b>deskripsi produk</b> (atau ketik - untuk skip)\n\n"
                            f"✅ Kode: <code>{product_data['code']}</code>\n"
                            f"✅ Nama: <b>{product_data['name']}</b>\n"
                            f"✅ Harga: <b>{format_rupiah(product_data['price_cents'])}</b>\n"
                            f"✅ Stok: <b>{product_data['stock']}</b> pcs",
                            reply_markup=cancel_keyboard,
                            parse_mode=ParseMode.HTML,
                        )
                        return
                    elif step == "description":
                        # Save description and create product
                        description = text.strip() if text.strip() != "-" else ""
                        product_data["description"] = description

                        # Create product (without category_id)
                        try:
                            product_id = await add_product(
                                category_id=None,  # No category needed
                                code=product_data["code"],
                                name=product_data["name"],
                                description=product_data["description"],
                                price_cents=product_data["price_cents"],
                                stock=product_data["stock"],
                            )

                            response = (
                                f"✅ <b>Produk berhasil ditambahkan!</b>\n\n"
                                f"🆔 ID: <code>{product_id}</code>\n"
                                f"📦 Kode: <code>{product_data['code']}</code>\n"
                                f"📝 Nama: <b>{product_data['name']}</b>\n"
                                f"💰 Harga: <b>{format_rupiah(product_data['price_cents'])}</b>\n"
                                f"📊 Stok: <b>{product_data['stock']}</b> pcs\n"
                                f"📄 Deskripsi: {product_data['description'] or '-'}"
                            )

                            # Store for SNK prompt
                            context.user_data["pending_snk_product"] = {
                                "product_id": product_id,
                                "product_name": product_data["name"],
                            }

                            clear_admin_state(context.user_data)
                            await update.message.reply_text(
                                response, parse_mode=ParseMode.HTML
                            )

                            # Ask about SNK with inline keyboard
                            snk_keyboard = InlineKeyboardMarkup(
                                [
                                    [
                                        InlineKeyboardButton(
                                            "➕ Tambah SNK",
                                            callback_data=f"admin:add_snk:{product_id}",
                                        )
                                    ],
                                    [
                                        InlineKeyboardButton(
                                            "⏭ Skip", callback_data="admin:skip_snk"
                                        )
                                    ],
                                ]
                            )
                            await update.message.reply_text(
                                "📜 Apakah ingin menambahkan Syarat & Ketentuan (SNK) untuk produk ini?",
                                reply_markup=snk_keyboard,
                                parse_mode=ParseMode.HTML,
                            )
                            return
                        except Exception as exc:
                            logger.exception("Error adding product: %s", exc)
                            await update.message.reply_text(
                                f"❌ Gagal menambahkan produk: {exc}",
                                parse_mode=ParseMode.HTML,
                            )
                            clear_admin_state(context.user_data)
                            return

                    return
                elif state.action == "edit_product_value":
                    # Handle field value input for edit product
                    product_id = state.payload.get("product_id")
                    field = state.payload.get("field")
                    value = text.strip()

                    cancel_keyboard = InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "❌ Batal", callback_data="admin:cancel"
                                )
                            ]
                        ]
                    )

                    try:
                        if field == "name":
                            await edit_product(product_id, name=value)
                            response = f"✅ Nama produk berhasil diupdate menjadi: <b>{value}</b>"
                        elif field == "price":
                            price_cents = parse_price_to_cents(value)
                            await edit_product(product_id, price_cents=price_cents)
                            response = f"✅ Harga produk berhasil diupdate menjadi: <b>{format_rupiah(price_cents)}</b>"
                        elif field == "stock":
                            stock = int(value)
                            await edit_product(product_id, stock=stock)
                            response = f"✅ Stok produk berhasil diupdate menjadi: <b>{stock}</b> pcs"
                        elif field == "description":
                            await edit_product(product_id, description=value)
                            response = f"✅ Deskripsi produk berhasil diupdate"
                        else:
                            response = "❌ Field tidak dikenali."

                        clear_admin_state(context.user_data)
                        await update.message.reply_text(
                            response,
                            parse_mode=ParseMode.HTML,
                        )
                        return
                    except ValueError:
                        await update.message.reply_text(
                            "❌ Nilai tidak valid. Pastikan format benar.",
                            reply_markup=cancel_keyboard,
                            parse_mode=ParseMode.HTML,
                        )
                        return
                    except Exception as exc:
                        logger.exception("Error updating product: %s", exc)
                        await update.message.reply_text(
                            f"❌ Gagal mengupdate produk: {exc}",
                            parse_mode=ParseMode.HTML,
                        )
                        clear_admin_state(context.user_data)
                        return
                elif state.action == "add_product_snk_choice":
                    await _handle_add_product_snk_choice(update, context, state, text)
                    return
                elif state.action == "add_product_snk_input":
                    product_id = int(state.payload.get("product_id") or 0)
                    if not product_id:
                        response = "⚠️ Produk untuk SNK tidak ditemukan."
                    else:
                        # Handle delete SNK
                        if text.strip().lower() == "hapus":
                            await clear_product_terms(product_id)
                            response = f"✅ SNK produk berhasil dihapus."
                        else:
                            response = await save_product_snk(product_id, text, user.id)
                    reply_kwargs["reply_markup"] = ReplyKeyboardRemove()
                elif state.action == "generate_voucher":
                    response = await handle_generate_voucher_input(text, user.id)  # type: ignore[arg-type]
                elif state.action == "delete_voucher":
                    response = await handle_delete_voucher_input(text, user.id)  # type: ignore[arg-type]
                elif state.action == "edit_cara_order_message":
                    stripped = text.strip()
                    if not stripped:
                        response = "⚠️ Teks Cara Order tidak boleh kosong."
                    else:
                        await _save_cara_order_template(
                            context,
                            text=stripped,
                            actor_id=user.id,
                            photo_file_id=None,
                        )
                        response = (
                            "✅ Template <b>Cara Order</b> berhasil diperbarui.\n"
                            "<i>Kirim foto + caption bila ingin menambahkan gambar panduan.</i>"
                        )
                    reply_kwargs["parse_mode"] = ParseMode.HTML
                # Handle refund calculator states
                elif "refund_calculator_state" in context.user_data:
                    calc_state = context.user_data["refund_calculator_state"]
                    if calc_state == "waiting_price":
                        try:
                            harga = int(text.strip())
                            context.user_data["refund_harga"] = harga
                            context.user_data["refund_calculator_state"] = (
                                "waiting_days"
                            )
                            cancel_keyboard = InlineKeyboardMarkup(
                                [
                                    [
                                        InlineKeyboardButton(
                                            "❌ Batal", callback_data="admin:cancel"
                                        )
                                    ]
                                ]
                            )
                            await update.message.reply_text(
                                f"✅ Harga: <b>{format_rupiah(harga * 100)}</b>\n\n"
                                "Sekarang masukkan <b>sisa hari</b> berlaku (contoh: 15):",
                                reply_markup=cancel_keyboard,
                                parse_mode=ParseMode.HTML,
                            )
                            return
                        except ValueError:
                            await update.message.reply_text(
                                "❌ Harga harus berupa angka. Coba lagi:",
                                parse_mode=ParseMode.HTML,
                            )
                            return
                    elif calc_state == "waiting_days":
                        try:
                            sisa_hari = int(text.strip())
                            harga = context.user_data.get("refund_harga", 0)
                            config = load_config()
                            refund = calculate_refund(harga, sisa_hari, config)

                            # Save to history
                            add_history(harga, sisa_hari, refund, user.id)

                            # Clear state
                            context.user_data.pop("refund_calculator_state", None)
                            context.user_data.pop("refund_harga", None)

                            await update.message.reply_text(
                                f"🧮 <b>Hasil Perhitungan Refund</b>\n\n"
                                f"💰 Harga: <b>{format_rupiah(harga * 100)}</b>\n"
                                f"📅 Sisa Hari: <b>{sisa_hari}</b> hari\n"
                                f"↩️ <b>Refund: {format_rupiah(refund * 100)}</b>\n\n"
                                f"Formula: <code>{config.get('formula', 'harga * (sisa_hari / 30)')}</code>",
                                parse_mode=ParseMode.HTML,
                            )
                            return
                        except ValueError:
                            await update.message.reply_text(
                                "❌ Sisa hari harus berupa angka. Coba lagi:",
                                parse_mode=ParseMode.HTML,
                            )
                            return
                        except Exception as exc:
                            logger.exception("Error calculating refund: %s", exc)
                            context.user_data.pop("refund_calculator_state", None)
                            context.user_data.pop("refund_harga", None)
                            await update.message.reply_text(
                                f"❌ Error dalam perhitungan: {exc}",
                                parse_mode=ParseMode.HTML,
                            )
                            return
                # Handle calculator formula setup
                elif "calculator_formula_state" in context.user_data:
                    formula_state = context.user_data["calculator_formula_state"]
                    if formula_state == "waiting_formula":
                        try:
                            new_formula = text.strip()
                            # Validate formula (basic check)
                            if (
                                "harga" not in new_formula
                                or "sisa_hari" not in new_formula
                            ):
                                await update.message.reply_text(
                                    "❌ Formula harus mengandung variabel <code>harga</code> dan <code>sisa_hari</code>",
                                    parse_mode=ParseMode.HTML,
                                )
                                return

                            # Update config
                            update_config({"formula": new_formula})
                            context.user_data.pop("calculator_formula_state", None)

                            await update.message.reply_text(
                                f"✅ <b>Formula berhasil diupdate!</b>\n\n"
                                f"Formula baru: <code>{new_formula}</code>",
                                parse_mode=ParseMode.HTML,
                            )
                            return
                        except Exception as exc:
                            logger.exception("Error updating formula: %s", exc)
                            context.user_data.pop("calculator_formula_state", None)
                            await update.message.reply_text(
                                f"❌ Error mengupdate formula: {exc}",
                                parse_mode=ParseMode.HTML,
                            )
                            return
                elif state.action == "broadcast_message":
                    if text.strip().lower() in ["batal", "❌ batal broadcast"]:
                        response = "🚫 Broadcast dibatalkan."
                    elif not text:
                        response = "⚠️ Pesan broadcast tidak boleh kosong."
                        keep_state = True
                    else:
                        result = await _schedule_broadcast_job(
                            context,
                            actor_id=user.id,
                            text=text,
                        )
                        if "job_id" not in result:
                            response = result.get(
                                "message",
                                "⚠️ Broadcast gagal dijadwalkan.",
                            )
                            keep_state = True
                        else:
                            response = _format_broadcast_summary(
                                int(result["job_id"]),
                                result.get("counts", {}),
                            )
                elif state.action == "update_order":
                    response = await handle_update_order_input(text, user.id)  # type: ignore[arg-type]
                elif state.action == "block_user":
                    response = await handle_block_user_input(text, user.id)  # type: ignore[arg-type]
                elif state.action == "unblock_user":
                    response = await handle_block_user_input(
                        text,
                        user.id,  # type: ignore[arg-type]
                        unblock=state.payload.get("unblock", False),
                    )
                else:
                    response = "⚠️ Aksi admin tidak dikenali."
                    clear_admin_state(context.user_data)
                    await update.message.reply_text(response)
                    return
            except AdminActionError as exc:
                await update.message.reply_text(f"❌ {exc}")
                return
            except Exception as exc:  # pragma: no cover - unexpected
                logger.exception("Gagal memproses aksi admin %s: %s", state.action, exc)
                clear_admin_state(context.user_data)
                await update.message.reply_text(
                    "⚠️ Terjadi kesalahan internal, coba lagi."
                )
                return
            clear_admin_state(context.user_data)
            if keep_state and state.action == "broadcast_message":
                set_admin_state(context.user_data, "broadcast_message")
            await update.message.reply_text(response, **reply_kwargs)
            # Removed old add_product SNK prompt - now handled in wizard
            return

    # Admin Settings - Main Entry Point
    if text == "⚙️ Admin Settings":
        if not is_admin:
            await update.message.reply_text("❌ Kamu tidak punya akses admin.")
            return
        from src.bot.admin.admin_menu import admin_settings_menu

        stats = await get_bot_statistics()
        await update.message.reply_text(
            f"⚙️ <b>Admin Settings</b>\n\n"
            f"👤 Total Pengguna: <b>{stats['total_users']}</b> orang\n"
            f"💰 Total Transaksi: <b>{stats['total_transactions']}</b>x\n\n"
            f"Pilih menu di bawah untuk mengelola bot:",
            reply_markup=admin_settings_menu(),
            parse_mode=ParseMode.HTML,
        )
        return

    # Admin menu handlers
    if text == "🛠 Kelola Respon Bot":
        if not is_admin:
            await update.message.reply_text("❌ Kamu tidak punya akses admin.")
            return
        from src.bot.admin.admin_menu import admin_response_menu

        await update.message.reply_text(
            "🛠 <b>Kelola Respon Bot</b>\n\n"
            "Kamu bisa mengubah template pesan yang dikirim bot.\n"
            "Pilih aksi di bawah:",
            reply_markup=admin_response_menu(),
            parse_mode=ParseMode.HTML,
        )
        return
    if text == "🛒 Kelola Produk":
        if not is_admin:
            await update.message.reply_text("❌ Kamu tidak punya akses admin.")
            return
        from src.bot.admin.admin_menu import admin_product_menu

        products = await list_products(limit=5)
        product_count = len(products)
        await update.message.reply_text(
            f"🛒 <b>Kelola Produk</b>\n\n"
            f"📦 Total Produk: <b>{product_count}</b>\n\n"
            f"Pilih aksi di bawah:",
            reply_markup=admin_product_menu(),
            parse_mode=ParseMode.HTML,
        )
        return
    if text == "📦 Kelola Order":
        if not is_admin:
            await update.message.reply_text("❌ Kamu tidak punya akses admin.")
            return
        from src.bot.admin.admin_menu import admin_order_menu

        await update.message.reply_text(
            "📦 <b>Kelola Order</b>\n\n"
            "Kelola pesanan customer di sini.\n"
            "Pilih aksi di bawah:",
            reply_markup=admin_order_menu(),
            parse_mode=ParseMode.HTML,
        )
        return
    if text == "👥 Kelola User":
        if not is_admin:
            await update.message.reply_text("❌ Kamu tidak punya akses admin.")
            return
        from src.bot.admin.admin_menu import admin_user_menu
        from src.services.users import list_users

        users = await list_users(limit=10)
        blocked_count = sum(1 for u in users if u.get("is_blocked", False))
        await update.message.reply_text(
            f"👥 <b>Kelola User</b>\n\n"
            f"📊 Total User: <b>{len(users)}</b>\n"
            f"🚫 Diblokir: <b>{blocked_count}</b>\n\n"
            f"Pilih aksi di bawah:",
            reply_markup=admin_user_menu(),
            parse_mode=ParseMode.HTML,
        )
        return
    if text == "🎟️ Kelola Voucher":
        if not is_admin:
            await update.message.reply_text("❌ Kamu tidak punya akses admin.")
            return
        from src.bot.admin.admin_menu import admin_voucher_menu

        await update.message.reply_text(
            "🎟️ <b>Kelola Voucher</b>\n\n"
            "Buat dan kelola voucher diskon di sini.\n"
            "Pilih aksi di bawah:",
            reply_markup=admin_voucher_menu(),
            parse_mode=ParseMode.HTML,
        )
        return
    if text == "⬅️ Kembali ke Menu Utama":
        if user:
            await _send_welcome_message(update, context, user)
        return

    if text == "🛍 Semua Produk":
        products = await list_products()
        await handle_product_list(update.message, context, products, "Semua Produk")
        return

    if text == "🏷 Cek Stok":
        products = await list_products()
        _store_products(context, products)
        settings = get_settings()
        stock_message = _build_stock_overview_message(
            products[:10], tz_name=settings.bot_timezone
        )
        await update.message.reply_text(
            stock_message,
            reply_markup=keyboards.stock_refresh_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        return
    if text == "📣 Broadcast Pesan":
        if not is_admin:
            await update.message.reply_text("❌ Kamu tidak punya akses admin.")
            return

        # Get broadcast stats
        targets = await list_broadcast_targets()
        total_users = await get_bot_statistics()
        blocked_count = total_users["total_users"] - len(targets)

        set_admin_state(context.user_data, "broadcast_message")

        cancel_keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ Batal Broadcast", callback_data="admin:cancel")]]
        )

        await update.message.reply_text(
            f"📣 <b>Mode Broadcast Aktif</b>\n\n"
            f"📊 <b>Statistik:</b>\n"
            f"👥 Total Pengguna: <b>{total_users['total_users']}</b>\n"
            f"✅ Akan Menerima: <b>{len(targets)}</b>\n"
            f"🚫 Diblokir: <b>{blocked_count}</b>\n\n"
            f"📝 <b>Cara Pakai:</b>\n"
            f"• Kirim <b>teks</b> untuk broadcast pesan\n"
            f"• Kirim <b>foto + caption</b> untuk broadcast gambar\n\n"
            f"Tekan tombol <b>❌ Batal Broadcast</b> di bawah untuk membatalkan.",
            reply_markup=cancel_keyboard,
            parse_mode=ParseMode.HTML,
        )
        return

    if text == "💰 Deposit":
        deposit_keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("💳 Deposit QRIS", callback_data="deposit:qris")],
                [
                    InlineKeyboardButton(
                        "📝 Transfer Manual", callback_data="deposit:manual"
                    )
                ],
            ]
        )

        await update.message.reply_text(
            "💼 <b>Menu Deposit</b>\n\n"
            "💰 Tambah saldo untuk transaksi lebih cepat!\n\n"
            "<b>📝 Cara Deposit:</b>\n"
            "• <b>QRIS:</b> Otomatis & instan\n"
            "• <b>Transfer Manual:</b> Kirim bukti ke admin\n\n"
            "Pilih metode di bawah:",
            reply_markup=deposit_keyboard,
            parse_mode=ParseMode.HTML,
        )
        return

    # Handle text-based cancel buttons (legacy support)
    if text in ["❌ Batal", "❌ Batal Broadcast"]:
        clear_admin_state(context.user_data)

        await update.message.reply_text(
            "✅ <b>Dibatalkan.</b>",
            parse_mode=ParseMode.HTML,
        )

        if user:
            await _send_welcome_message(update, context, user)
        return

    if text == "⬅️ Kembali":
        if user:
            await _send_welcome_message(update, context, user)
        return

    # Handler untuk tombol Calculator (admin only)
    if text == "🧮 Calculator":
        if not is_admin:
            await update.message.reply_text("❌ Kamu tidak punya akses admin.")
            return

        calc_keyboard = ReplyKeyboardMarkup(
            [
                ["🔢 Hitung Refund"],
                ["⚙️ Atur Formula"],
                ["📜 Riwayat Kalkulasi"],
                ["⬅️ Kembali"],
            ],
            resize_keyboard=True,
        )

        await update.message.reply_text(
            "🧮 <b>Kalkulator Refund</b>\n\n"
            "💡 <b>Fungsi:</b>\n"
            "• Hitung refund otomatis berdasarkan sisa hari\n"
            "• Atur formula kustom untuk perhitungan\n"
            "• Lihat riwayat kalkulasi sebelumnya\n\n"
            "Pilih menu di bawah:",
            reply_markup=calc_keyboard,
            parse_mode=ParseMode.HTML,
        )
        return

    if text == "🔢 Hitung Refund":
        if not is_admin:
            await update.message.reply_text("❌ Kamu tidak punya akses admin.")
            return
        # Directly start refund calculator
        cancel_keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ Batal", callback_data="admin:cancel")]]
        )
        await update.message.reply_text(
            "🧮 <b>Kalkulator Refund</b>\n\n"
            "Masukkan <b>harga langganan</b> (contoh: 50000):",
            reply_markup=cancel_keyboard,
            parse_mode=ParseMode.HTML,
        )
        context.user_data["refund_calculator_state"] = "waiting_price"
        return

    if text == "⚙️ Atur Formula":
        if not is_admin:
            await update.message.reply_text("❌ Kamu tidak punya akses admin.")
            return
        # Directly start formula setup
        cancel_keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ Batal", callback_data="admin:cancel")]]
        )
        config = load_config()
        await update.message.reply_text(
            "⚙️ <b>Atur Formula Refund</b>\n\n"
            f"Formula saat ini: <code>{config.get('formula', 'harga * (sisa_hari / 30)')}</code>\n\n"
            "Kirim formula baru (contoh: <code>harga * (sisa_hari / 30)</code>)\n\n"
            "💡 Variabel yang tersedia:\n"
            "• <code>harga</code> - Harga langganan\n"
            "• <code>sisa_hari</code> - Sisa hari berlaku",
            reply_markup=cancel_keyboard,
            parse_mode=ParseMode.HTML,
        )
        context.user_data["calculator_formula_state"] = "waiting_formula"
        return

    if text == "📜 Riwayat Kalkulasi":
        if not is_admin:
            await update.message.reply_text("❌ Kamu tidak punya akses admin.")
            return
        await update.message.reply_text(
            "Gunakan command: <code>/refund_history</code>",
            parse_mode=ParseMode.HTML,
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
            await update.message.reply_text(
                "❓ Produk belum tersedia, coba pilih yang lain ya."
            )
        return

    await update.message.reply_text(messages.generic_error(), parse_mode=ParseMode.HTML)


async def media_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle media messages (currently for SNK submissions)."""
    message = update.message
    if message is None:
        return
    if await _check_spam(update, context):
        return
    if message.photo:
        file_id = message.photo[-1].file_id
        caption = (message.caption or "").strip()
        if await _handle_snk_submission_message(
            message,
            context,
            text=caption,
            media_file_id=file_id,
            media_type="photo",
        ):
            return
    if message.photo and context.user_data.get("profile_edit"):
        await message.reply_text(
            "⚠️ Kirimkan data dalam bentuk teks ya. Foto tidak diperlukan untuk pengaturan profil.",
            parse_mode=ParseMode.HTML,
        )
        return
    user = update.effective_user
    admin_ids = context.bot_data.get("admin_ids", [])
    if user and str(user.id) in admin_ids and message.photo:
        state = get_admin_state(context.user_data)
        if state:
            if state.action == "broadcast_message":
                file_id = message.photo[-1].file_id
                caption = (message.caption or "").strip()
                result = await _schedule_broadcast_job(
                    context,
                    actor_id=user.id,
                    text=caption,
                    media_file_id=file_id,
                    media_type="photo",
                )
                clear_admin_state(context.user_data)
                if "job_id" not in result:
                    await message.reply_text(
                        result.get("message", "⚠️ Broadcast gagal dijadwalkan."),
                        reply_markup=ReplyKeyboardRemove(),
                    )
                else:
                    await message.reply_text(
                        _format_broadcast_summary(
                            int(result["job_id"]),
                            result.get("counts", {}),
                        ),
                        reply_markup=ReplyKeyboardRemove(),
                    )
                return
            if state.action == "edit_cara_order_message":
                file_id = message.photo[-1].file_id
                caption = (message.caption or "").strip()
                if not caption:
                    await message.reply_text(
                        "⚠️ Mohon sertakan caption saat mengirim foto untuk template Cara Order.",
                        parse_mode=ParseMode.HTML,
                    )
                    return
                await _save_cara_order_template(
                    context,
                    text=caption,
                    actor_id=user.id,
                    photo_file_id=file_id,
                )
                clear_admin_state(context.user_data)
                await message.reply_text(
                    "✅ Template <b>Cara Order</b> berhasil diperbarui dengan gambar.",
                    parse_mode=ParseMode.HTML,
                )
                return


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

    if data.startswith("snk:submit:"):
        try:
            notification_id = int(data.split(":", maxsplit=2)[2])
        except (IndexError, ValueError):
            await query.answer("Permintaan tidak valid.", show_alert=True)
            return
        notification = await get_notification(notification_id)
        if notification is None:
            await query.answer("Permintaan SNK sudah tidak aktif.", show_alert=True)
            return
        if int(notification["telegram_user_id"]) != user.id:
            await query.answer("Permintaan SNK tidak cocok.", show_alert=True)
            return
        context.user_data["snk_submission"] = {"notification_id": notification_id}
        await query.answer("Silakan kirim bukti SNK kamu.")
        await query.message.reply_text(
            "📸 Kirim screenshot dan keterangan sesuai SNK ya. Kamu juga boleh kirim teks saja kalau tidak perlu screenshot."
        )
        return

    if data == "stock:refresh":
        products = await list_products()
        _store_products(context, products)
        settings = get_settings()
        stock_message = _build_stock_overview_message(
            products[:10], tz_name=settings.bot_timezone
        )
        try:
            await query.message.edit_text(
                stock_message,
                reply_markup=keyboards.stock_refresh_keyboard(),
                parse_mode=ParseMode.HTML,
            )
        except TelegramError:
            await query.message.reply_text(
                stock_message,
                reply_markup=keyboards.stock_refresh_keyboard(),
                parse_mode=ParseMode.HTML,
            )
        await query.answer("Stok diperbarui")
        return

    if data == "welcome:info":
        profile = await get_user_profile(user.id)
        message_text = _build_user_info_message(profile, user=user)
        await query.answer()
        await query.message.reply_text(
            message_text,
            reply_markup=keyboards.info_menu_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        return

    if data == "welcome:howto":
        profile = await get_user_profile(user.id)
        display_name = _extract_display_name(profile, user)
        text_template, photo_id = await _get_cara_order_template(context)
        settings = get_settings()
        rendered = _apply_template(
            text_template,
            nama=display_name,
            store_name=settings.store_name,
        )
        await query.answer()
        if photo_id:
            await query.message.reply_photo(
                photo=photo_id,
                caption=rendered,
                parse_mode=ParseMode.HTML,
            )
        else:
            await query.message.reply_text(
                rendered,
                parse_mode=ParseMode.HTML,
            )
        return

    if data.startswith("profile:"):
        await query.answer()
        settings = get_settings()
        profile = await get_user_profile(user.id)
        if data == "profile:settings":
            context.user_data.pop("profile_edit", None)
            await query.message.reply_text(
                _build_profile_settings_message(profile, user),
                reply_markup=keyboards.info_settings_keyboard(),
                parse_mode=ParseMode.HTML,
            )
            return
        if data == "profile:cs":
            await query.message.reply_text(
                _build_customer_service_message(settings),
                reply_markup=keyboards.info_menu_keyboard(),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            return
        if data == "profile:last":
            summary = await _build_last_transaction_message(user.id, settings=settings)
            await query.message.reply_text(
                summary,
                reply_markup=keyboards.info_menu_keyboard(),
                parse_mode=ParseMode.HTML,
            )
            return
        if data == "profile:change_username":
            context.user_data["profile_edit"] = {"field": "display_name"}
            await query.message.reply_text(
                "Kirim username baru kamu (3-32 karakter). Ketik <b>BATAL</b> untuk membatalkan.",
                parse_mode=ParseMode.HTML,
            )
            return
        if data == "profile:change_whatsapp":
            context.user_data["profile_edit"] = {"field": "whatsapp"}
            await query.message.reply_text(
                "Kirim nomor WhatsApp kamu tanpa spasi atau simbol. Ketik <b>BATAL</b> untuk membatalkan.",
                parse_mode=ParseMode.HTML,
            )
            return
        if data == "profile:cancel":
            context.user_data.pop("profile_edit", None)
            await query.message.reply_text(
                "✅ Pengaturan dibatalkan.",
                reply_markup=keyboards.info_menu_keyboard(),
                parse_mode=ParseMode.HTML,
            )
            return
        return

    # --- Admin Menu Callback Integration ---
    # Only allow admin_ids to access admin callbacks
    admin_ids = context.bot_data.get("admin_ids", [])
    if data.startswith("admin:") and str(user.id) in admin_ids:
        from src.bot.admin.admin_menu import (
            admin_response_menu,
            admin_product_menu,
            admin_order_menu,
            admin_user_menu,
        )

        if data == "admin:back":
            from src.bot.admin.admin_menu import admin_settings_menu

            stats = await get_bot_statistics()
            await update.effective_message.reply_text(
                f"⚙️ <b>Admin Settings</b>\n\n"
                f"👤 Total Pengguna: <b>{stats['total_users']}</b> orang\n"
                f"💰 Total Transaksi: <b>{stats['total_transactions']}</b>x\n\n"
                f"Pilih menu di bawah:",
                reply_markup=admin_settings_menu(),
                parse_mode=ParseMode.HTML,
            )
            return
        elif data == "admin:preview_responses":
            await update.effective_message.reply_text(
                "👁️ <b>Preview Template Messages</b>\n\n"
                "<b>🌟 Welcome Message:</b>\n"
                "Hai {nama}! Selamat datang di {store_name}!\n\n"
                "<b>🎉 Payment Success:</b>\n"
                "Pembayaran berhasil untuk order {order_id}!\n\n"
                "<b>📘 Cara Order:</b>\n"
                "1. Pilih produk favorit kamu\n"
                "2. Tambahkan ke keranjang\n"
                "3. Selesaikan pembayaran sebelum waktu habis\n\n"
                "<b>⚠️ Error Message:</b>\n"
                "Maaf, terjadi kesalahan. Coba lagi ya!\n\n"
                "<b>📦 Product Message:</b>\n"
                "Produk: {nama_produk}\n"
                "Harga: {harga}\n"
                "Stok: {stok}x",
                parse_mode=ParseMode.HTML,
            )
            return
        elif data == "admin:add_product":
            set_admin_state(context.user_data, "add_product_step", step="code")
            cancel_keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Batal", callback_data="admin:cancel")]]
            )
            await update.effective_message.reply_text(
                "➕ <b>Tambah Produk Baru</b>\n\n"
                "Langkah 1/5: Kirim <b>kode produk</b> (contoh: NETFLIX1M, SPOTIFY1T)\n\n"
                "💡 Kode produk adalah identifikasi unik untuk produk ini.",
                reply_markup=cancel_keyboard,
                parse_mode=ParseMode.HTML,
            )
            return
        elif data == "admin:edit_product":
            products = await list_products(limit=50)
            if not products:
                await update.effective_message.reply_text(
                    "❌ Belum ada produk yang bisa diedit.",
                    parse_mode=ParseMode.HTML,
                )
                return

            set_admin_state(context.user_data, "edit_product_step", step="select")

            # Show product list with inline buttons
            buttons = []
            for p in products[:20]:  # Limit to 20 for UI
                buttons.append(
                    [
                        InlineKeyboardButton(
                            f"{p.name} - {format_rupiah(p.price_cents)}",
                            callback_data=f"admin:edit_product_select:{p.id}",
                        )
                    ]
                )
            buttons.append(
                [InlineKeyboardButton("❌ Batal", callback_data="admin:cancel")]
            )

            await update.effective_message.reply_text(
                "📝 <b>Edit Produk</b>\n\nPilih produk yang ingin diedit:",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.HTML,
            )
            return
        elif data == "admin:delete_product":
            products = await list_products(limit=50)
            if not products:
                await update.effective_message.reply_text(
                    "❌ Belum ada produk yang bisa dihapus.",
                    parse_mode=ParseMode.HTML,
                )
                return

            set_admin_state(context.user_data, "delete_product_step", step="select")

            # Show product list with inline buttons
            buttons = []
            for p in products[:20]:
                buttons.append(
                    [
                        InlineKeyboardButton(
                            f"🗑️ {p.name}",
                            callback_data=f"admin:delete_product_select:{p.id}",
                        )
                    ]
                )
            buttons.append(
                [InlineKeyboardButton("❌ Batal", callback_data="admin:cancel")]
            )

            await update.effective_message.reply_text(
                "🗑️ <b>Hapus Produk</b>\n\nPilih produk yang ingin dihapus:",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.HTML,
            )
            return
        elif data == "admin:snk_product":
            products = await list_products(limit=50)
            if not products:
                await update.effective_message.reply_text(
                    "❌ Belum ada produk.",
                    parse_mode=ParseMode.HTML,
                )
                return

            set_admin_state(context.user_data, "snk_product_step", step="select")

            # Show product list with inline buttons
            buttons = []
            for p in products[:20]:
                buttons.append(
                    [
                        InlineKeyboardButton(
                            f"{p.name}",
                            callback_data=f"admin:snk_product_select:{p.id}",
                        )
                    ]
                )
            buttons.append(
                [InlineKeyboardButton("❌ Batal", callback_data="admin:cancel")]
            )

            await update.effective_message.reply_text(
                "📜 <b>Kelola SNK Produk</b>\n\n"
                "Pilih produk untuk mengatur Syarat & Ketentuan:",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.HTML,
            )
            return
        elif data == "admin:snk_product":
            set_admin_state(context.user_data, "manage_product_snk")
            await update.effective_message.reply_text(
                "📜 Kelola SNK Produk\n"
                "Format: product_id|SNK baru\n"
                "Gunakan product_id|hapus untuk mengosongkan SNK.",
            )
            return
        elif data == "admin:list_orders":
            overview = await render_order_overview()
            await update.effective_message.reply_text(
                overview, parse_mode=ParseMode.HTML
            )
            return
        elif data == "admin:update_order":
            set_admin_state(context.user_data, "update_order")
            cancel_keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Batal", callback_data="admin:cancel")]]
            )
            await update.effective_message.reply_text(
                "🔄 <b>Update Status Order</b>\n\n"
                "Kirim format berikut:\n"
                "<code>order_id | status_baru | catatan (opsional)</code>\n\n"
                "<b>📝 Contoh:</b>\n"
                "<code>123 | paid | BNI Transfer #123456</code>\n"
                "<code>456 | cancelled | Stok habis</code>\n\n"
                "<b>Status yang tersedia:</b>\n"
                "• <code>paid</code> - Pembayaran sukses\n"
                "• <code>cancelled</code> - Pesanan dibatalkan\n"
                "• <code>completed</code> - Pesanan selesai\n\n"
                "💡 <b>Catatan:</b> Isi catatan jika ada keterangan pembayaran manual/deposit (nomor referensi, bank, dll)",
                reply_markup=cancel_keyboard,
                parse_mode=ParseMode.HTML,
            )
            return
        elif data == "admin:list_users":
            overview = await render_user_overview()
            await update.effective_message.reply_text(overview)
            return
        elif data == "admin:block_user":
            set_admin_state(context.user_data, "block_user")
            cancel_keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Batal", callback_data="admin:cancel")]]
            )
            await update.effective_message.reply_text(
                "🚫 <b>Blokir User</b>\n\n"
                "Kirim ID Telegram user yang ingin diblokir.\n\n"
                "📝 Contoh: <code>123456789</code>",
                reply_markup=cancel_keyboard,
                parse_mode=ParseMode.HTML,
            )
            return
        elif data == "admin:unblock_user":
            set_admin_state(context.user_data, "unblock_user", unblock=True)
            cancel_keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Batal", callback_data="admin:cancel")]]
            )
            await update.effective_message.reply_text(
                "✅ <b>Unblokir User</b>\n\n"
                "Kirim ID Telegram user yang ingin di-unblokir.\n\n"
                "📝 Contoh: <code>123456789</code>",
                reply_markup=cancel_keyboard,
                parse_mode=ParseMode.HTML,
            )
            return
        elif data == "admin:generate_voucher":
            set_admin_state(context.user_data, "generate_voucher")
            cancel_keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Batal", callback_data="admin:cancel")]]
            )
            await update.effective_message.reply_text(
                "➕ <b>Buat Voucher Baru</b>\n\n"
                "Kirim format sederhana:\n"
                "<b>KODE | NOMINAL | BATAS_PAKAI</b>\n\n"
                "📝 Contoh:\n"
                "<code>HEMAT10 | 10% | 100</code>\n"
                "<code>DISKON5K | 5000 | 50</code>",
                reply_markup=cancel_keyboard,
                parse_mode=ParseMode.HTML,
            )
            return
        elif data == "admin:list_vouchers":
            overview = await render_voucher_overview()
            await update.effective_message.reply_text(overview)
            return
        elif data == "admin:delete_voucher":
            set_admin_state(context.user_data, "delete_voucher")
            cancel_keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Batal", callback_data="admin:cancel")]]
            )
            await update.effective_message.reply_text(
                "🗑️ <b>Nonaktifkan Voucher</b>\n\n"
                "Kirim <b>ID voucher</b> yang ingin dinonaktifkan.",
                reply_markup=cancel_keyboard,
                parse_mode=ParseMode.HTML,
            )
            return
        elif data == "admin:edit_welcome":
            set_admin_state(context.user_data, "edit_welcome_message")
            cancel_keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Batal", callback_data="admin:cancel")]]
            )
            await update.effective_message.reply_text(
                "🌟 <b>Edit Welcome Message</b>\n\n"
                "Kirim pesan welcome baru kamu.\n"
                "Bisa kirim <b>teks biasa</b> atau <b>foto dengan caption</b>.\n\n"
                "💡 Placeholder yang bisa dipakai:\n"
                "• <code>{nama}</code> - Nama user\n"
                "• <code>{store_name}</code> - Nama toko\n"
                "• <code>{total_users}</code> - Total pengguna",
                reply_markup=cancel_keyboard,
                parse_mode=ParseMode.HTML,
            )
            return
        elif data == "admin:edit_cara_order":
            set_admin_state(context.user_data, "edit_cara_order_message")
            cancel_keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Batal", callback_data="admin:cancel")]]
            )
            await update.effective_message.reply_text(
                "📘 <b>Edit Cara Order</b>\n\n"
                "Kirim teks panduan baru atau foto dengan caption untuk mengganti template Cara Order.\n\n"
                "💡 Placeholder yang bisa dipakai:\n"
                "• <code>{nama}</code> - Nama pengguna\n"
                "• <code>{store_name}</code> - Nama toko\n\n"
                "Kirim <b>❌ Batal</b> untuk membatalkan.",
                reply_markup=cancel_keyboard,
                parse_mode=ParseMode.HTML,
            )
            return
        elif data == "admin:cancel":
            # Handle cancel button - clear all states and show welcome message
            clear_admin_state(context.user_data)
            context.user_data.pop("refund_calculator_state", None)
            context.user_data.pop("refund_harga", None)
            context.user_data.pop("calculator_formula_state", None)
            context.user_data.pop("pending_snk_product", None)

            await update.effective_message.edit_text(
                f"✅ <b>Dibatalkan.</b>",
                parse_mode=ParseMode.HTML,
            )

            if user:
                await _send_welcome_message(
                    update, context, user, update.effective_message
                )
            return
        elif data.startswith("admin:add_snk:"):
            # Handle add SNK for product
            product_id = int(data.split(":")[2])
            set_admin_state(
                context.user_data, "add_product_snk_input", product_id=product_id
            )
            cancel_keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Batal", callback_data="admin:cancel")]]
            )
            await update.effective_message.reply_text(
                "📜 <b>Tambah SNK Produk</b>\n\n"
                "Silakan kirim Syarat & Ketentuan untuk produk ini.\n"
                "Kamu bisa tulis beberapa baris untuk menjelaskan:\n"
                "• Aturan penggunaan\n"
                "• Langkah login/aktivasi\n"
                "• Batas waktu klaim\n"
                "• Garansi (jika ada)",
                reply_markup=cancel_keyboard,
                parse_mode=ParseMode.HTML,
            )
            return
        elif data == "admin:skip_snk":
            # Skip SNK after adding product
            clear_admin_state(context.user_data)
            context.user_data.pop("pending_snk_product", None)
            await update.effective_message.edit_text(
                "✅ <b>Produk berhasil ditambahkan tanpa SNK.</b>\n\n"
                "Kamu bisa menambahkan SNK nanti melalui menu <b>📜 Kelola SNK Produk</b>.",
                parse_mode=ParseMode.HTML,
            )
            return
        elif data.startswith("admin:edit_product_select:"):
            # Handle product selection for edit
            product_id = int(data.split(":")[2])
            product = await get_product(product_id)
            if not product:
                await update.effective_message.reply_text(
                    "❌ Produk tidak ditemukan.",
                    parse_mode=ParseMode.HTML,
                )
                return

            set_admin_state(
                context.user_data,
                "edit_product_field",
                product_id=product_id,
                step="field",
            )

            # Show edit menu
            edit_keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "📝 Edit Nama",
                            callback_data=f"admin:edit_field:name:{product_id}",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "💰 Edit Harga",
                            callback_data=f"admin:edit_field:price:{product_id}",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "📊 Edit Stok",
                            callback_data=f"admin:edit_field:stock:{product_id}",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "📄 Edit Deskripsi",
                            callback_data=f"admin:edit_field:description:{product_id}",
                        )
                    ],
                    [InlineKeyboardButton("❌ Batal", callback_data="admin:cancel")],
                ]
            )

            await update.effective_message.edit_text(
                f"📝 <b>Edit Produk</b>\n\n"
                f"<b>Produk:</b> {product.name}\n"
                f"<b>Harga:</b> {format_rupiah(product.price_cents)}\n"
                f"<b>Stok:</b> {product.stock} pcs\n\n"
                f"Pilih field yang ingin diedit:",
                reply_markup=edit_keyboard,
                parse_mode=ParseMode.HTML,
            )
            return
        elif data.startswith("admin:edit_field:"):
            # Handle field selection for edit
            parts = data.split(":")
            field = parts[2]
            product_id = int(parts[3])

            set_admin_state(
                context.user_data,
                "edit_product_value",
                product_id=product_id,
                field=field,
            )
            cancel_keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Batal", callback_data="admin:cancel")]]
            )

            field_names = {
                "name": "nama produk",
                "price": "harga (contoh: 50000)",
                "stock": "stok (contoh: 100)",
                "description": "deskripsi produk",
            }

            await update.effective_message.reply_text(
                f"📝 <b>Edit {field_names.get(field, field)}</b>\n\n"
                f"Kirim nilai baru untuk {field_names.get(field, field)}:",
                reply_markup=cancel_keyboard,
                parse_mode=ParseMode.HTML,
            )
            return
        elif data.startswith("admin:delete_product_select:"):
            # Handle product selection for delete
            product_id = int(data.split(":")[2])
            product = await get_product(product_id)
            if not product:
                await update.effective_message.reply_text(
                    "❌ Produk tidak ditemukan.",
                    parse_mode=ParseMode.HTML,
                )
                return

            # Confirm deletion
            confirm_keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "✅ Ya, Hapus",
                            callback_data=f"admin:delete_product_confirm:{product_id}",
                        )
                    ],
                    [InlineKeyboardButton("❌ Batal", callback_data="admin:cancel")],
                ]
            )

            await update.effective_message.edit_text(
                f"🗑️ <b>Konfirmasi Hapus Produk</b>\n\n"
                f"<b>Produk:</b> {product.name}\n"
                f"<b>Harga:</b> {format_rupiah(product.price_cents)}\n"
                f"<b>Stok:</b> {product.stock} pcs\n\n"
                f"⚠️ <b>Peringatan:</b> Produk yang sudah dihapus tidak bisa dikembalikan!\n\n"
                f"Yakin ingin menghapus produk ini?",
                reply_markup=confirm_keyboard,
                parse_mode=ParseMode.HTML,
            )
            return
        elif data.startswith("admin:delete_product_confirm:"):
            # Handle delete confirmation
            product_id = int(data.split(":")[2])
            try:
                await delete_product(product_id)
                await update.effective_message.edit_text(
                    f"✅ <b>Produk berhasil dihapus!</b>\n\n"
                    f"Produk dengan ID <code>{product_id}</code> telah dihapus dari database.",
                    parse_mode=ParseMode.HTML,
                )
            except Exception as exc:
                logger.exception("Error deleting product: %s", exc)
                await update.effective_message.edit_text(
                    f"❌ Gagal menghapus produk: {exc}",
                    parse_mode=ParseMode.HTML,
                )
            return
        elif data.startswith("admin:snk_product_select:"):
            # Handle product selection for SNK management
            product_id = int(data.split(":")[2])
            product = await get_product(product_id)
            if not product:
                await update.effective_message.reply_text(
                    "❌ Produk tidak ditemukan.",
                    parse_mode=ParseMode.HTML,
                )
                return

            set_admin_state(
                context.user_data, "add_product_snk_input", product_id=product_id
            )
            cancel_keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Batal", callback_data="admin:cancel")]]
            )

            await update.effective_message.reply_text(
                f"📜 <b>Kelola SNK: {product.name}</b>\n\n"
                f"Kirim SNK baru untuk produk ini.\n"
                f"Atau ketik <code>hapus</code> untuk menghapus SNK yang ada.",
                reply_markup=cancel_keyboard,
                parse_mode=ParseMode.HTML,
            )
            return
        elif data == "admin:edit_payment_success":
            set_admin_state(context.user_data, "edit_payment_success")
            cancel_keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Batal", callback_data="admin:cancel")]]
            )
            await update.effective_message.reply_text(
                "🎉 <b>Edit Payment Success Message</b>\n\n"
                "Kirim pesan sukses pembayaran baru.\n"
                "Bisa kirim <b>teks biasa</b> atau <b>foto dengan caption</b>.\n\n"
                "💡 Placeholder:\n"
                "• <code>{order_id}</code> - ID Order\n"
                "• <code>{nama}</code> - Nama pembeli\n\n"
                "Ketik <b>❌ Batal</b> untuk membatalkan.",
                reply_markup=cancel_keyboard,
                parse_mode=ParseMode.HTML,
            )
            return
        elif data == "admin:edit_error":
            set_admin_state(context.user_data, "edit_error_message")
            cancel_keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Batal", callback_data="admin:cancel")]]
            )
            await update.effective_message.reply_text(
                "⚠️ <b>Edit Error Message</b>\n\n"
                "Kirim pesan error baru yang akan ditampilkan saat ada masalah.\n\n"
                "Ketik <b>❌ Batal</b> untuk membatalkan.",
                reply_markup=cancel_keyboard,
                parse_mode=ParseMode.HTML,
            )
            return
        elif data == "admin:edit_product":
            set_admin_state(context.user_data, "edit_product_message")
            cancel_keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Batal", callback_data="admin:cancel")]]
            )
            await update.effective_message.reply_text(
                "📦 <b>Edit Product Message</b>\n\n"
                "📦 <b>Edit Product Message Template</b>\n\n"
                "Kirim template pesan produk baru.\n\n"
                "💡 Placeholder:\n"
                "• <code>{nama_produk}</code> - Nama produk\n"
                "• <code>{harga}</code> - Harga produk\n"
                "• <code>{stok}</code> - Stok tersedia\n\n"
                "Ketik <b>❌ Batal</b> untuk membatalkan.",
                reply_markup=cancel_keyboard,
                parse_mode=ParseMode.HTML,
            )
            return
        # Submenu navigation
        elif data == "admin:response_menu":
            await update.effective_message.reply_text(
                "🛠 Kelola Respon Bot", reply_markup=admin_response_menu()
            )
            return
        elif data == "admin:product_menu":
            overview = await render_product_overview()
            await update.effective_message.reply_text(overview)
            await update.effective_message.reply_text(
                "🛒 Kelola Produk", reply_markup=admin_product_menu()
            )
            return
        elif data == "admin:order_menu":
            overview = await render_order_overview()
            await update.effective_message.reply_text(
                overview, parse_mode=ParseMode.HTML
            )
            await update.effective_message.reply_text(
                "📦 Kelola Order", reply_markup=admin_order_menu()
            )
            return
        elif data == "admin:user_menu":
            overview = await render_user_overview()
            await update.effective_message.reply_text(overview)
            await update.effective_message.reply_text(
                "👥 Kelola User", reply_markup=admin_user_menu()
            )
            return
    # --- End Admin Menu Callback Integration ---

    # --- Deposit Handlers ---
    if data.startswith("deposit:"):
        action = data.split(":", maxsplit=1)[1]
        if action == "qris":
            await query.answer()
            await query.message.reply_text(
                "💳 <b>Deposit via QRIS</b>\n\n"
                "🔄 Fitur deposit QRIS sedang dalam pengembangan.\n\n"
                "Untuk sementara, silakan gunakan metode <b>Transfer Manual</b> "
                "atau hubungi admin untuk top-up saldo.\n\n"
                "📱 Akan segera hadir dalam update mendatang!",
                parse_mode=ParseMode.HTML,
            )
            return
        elif action == "manual":
            await query.answer()
            settings = get_settings()
            # Get admin info for transfer (use admin_ids, not owner_ids)
            admin_contact = "admin"  # Default
            if settings.telegram_admin_ids:
                admin_id = settings.telegram_admin_ids[0]
                admin_contact = f'<a href="tg://user?id={admin_id}">admin</a>'
            elif settings.telegram_owner_ids:
                # Fallback to owner if no admin configured
                owner_id = settings.telegram_owner_ids[0]
                admin_contact = f'<a href="tg://user?id={owner_id}">owner</a>'

            await query.message.reply_text(
                "📝 <b>Deposit via Transfer Manual</b>\n\n"
                "💰 <b>Cara Deposit:</b>\n"
                "1. Transfer ke rekening yang diberikan admin\n"
                "2. Screenshot bukti transfer\n"
                "3. Kirim bukti ke admin dengan mention jumlah\n"
                "4. Tunggu konfirmasi (max 1x24 jam)\n\n"
                "👤 <b>Hubungi Admin:</b>\n"
                f"Silakan hubungi {admin_contact} untuk detail rekening "
                "dan konfirmasi deposit.\n\n"
                "💡 <b>Tips:</b>\n"
                "• Sertakan username Telegram kamu\n"
                "• Cantumkan nominal yang ditransfer\n"
                "• Simpan bukti transfer sampai dikonfirmasi\n\n"
                "⚡ Saldo akan masuk otomatis setelah admin konfirmasi!",
                parse_mode=ParseMode.HTML,
            )
            return
    # --- End Deposit Handlers ---

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
        await handle_product_list(query.message, context, products, title)
        return

    if data.startswith("products:page:"):
        try:
            page = int(data.split(":", maxsplit=2)[2])
            products = context.user_data.get("product_list", [])
            if not products:
                products = await list_products()
            await handle_product_list(
                query.message, context, products, "Semua Produk", page=page
            )
        except (IndexError, ValueError) as exc:
            logger.error("Invalid page callback: %s", exc)
            await query.answer("❌ Halaman tidak valid", show_alert=True)
        return

    if data.startswith("product:"):
        try:
            product_id = int(data.split(":", maxsplit=1)[1])
            product = await get_product(product_id)
            if product is None:
                await query.answer("❌ Produk tidak ditemukan", show_alert=True)
                return
            item = cart.items.get(product.id)
            quantity = item.quantity if item else 0
            await query.message.reply_text(
                messages.product_detail(product, quantity),
                reply_markup=keyboards.product_inline_keyboard(product, quantity),
                parse_mode=ParseMode.HTML,
            )
        except (IndexError, ValueError) as exc:
            logger.error("Invalid product callback: %s", exc)
            await query.answer("❌ Produk tidak valid", show_alert=True)
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
                parse_mode=ParseMode.HTML,
            )
            return

        if action == "checkout":
            total_items = cart.total_items()
            total_rp = format_rupiah(cart.total_cents())
            lines = cart.to_lines()
            await query.message.reply_text(
                messages.cart_summary(lines, total_items, total_rp),
                reply_markup=keyboards.cart_inline_keyboard(),
                parse_mode=ParseMode.HTML,
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
                parse_mode=ParseMode.HTML,
            )
            return

    if data.startswith("pay:"):
        action = data.split(":", maxsplit=1)[1]
        payment_service = get_payment_service(context)
        telemetry = get_telemetry(context)
        cart = await cart_manager.get_cart(user.id)
        if action == "qris":
            # Show loading message
            loading_msg = await query.message.reply_text(
                messages.payment_loading(), parse_mode=ParseMode.HTML
            )

            try:
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
                await loading_msg.edit_text(f"⚠️ {exc}", parse_mode=ParseMode.HTML)
                return

            payment_data = payload["payment"]
            invoice_text = messages.payment_invoice_detail(
                invoice_id=gateway_order_id,
                items=cart.to_lines(),
                total_rp=format_rupiah(cart.total_cents()),
                expires_in="5 Menit",
                created_at=payload["created_at"],
            )

            # Send invoice to user first
            qr_data = str(payment_data.get("payment_number", ""))
            if qr_data:
                invoice_message = await query.message.reply_photo(
                    photo=qris_to_image(qr_data),
                    caption=invoice_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboards.invoice_keyboard(payload["payment_url"]),
                )
            else:
                invoice_message = await query.message.reply_text(
                    invoice_text
                    + "\n\n(⚠️ QR tidak tersedia, gunakan tautan checkout.)",
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboards.invoice_keyboard(payload["payment_url"]),
                )

            await record_payment_message(
                gateway_order_id=gateway_order_id,
                chat_id=invoice_message.chat_id,
                message_id=invoice_message.message_id,
                role="user_invoice",
                message_kind="photo" if qr_data else "text",
            )

            # Delete loading message
            try:
                await loading_msg.delete()
            except Exception:
                pass

            # Then notify admin
            await _notify_admin_new_order(
                context,
                user,
                cart,
                order_id=str(payload.get("order_id", "")),
                method=action,
                created_at=str(payload.get("created_at")),
                gateway_order_id=gateway_order_id,
            )

            # Clear cart after successful payment creation
            await cart_manager.clear_cart(user.id)
            return
        if action == "balance":
            await query.message.reply_text(
                "💼 Saldo belum tersedia. Coba pakai QRIS dulu ya!"
            )
            return
        if action == "cancel":
            await cart_manager.clear_cart(user.id)
            await query.message.reply_text(
                messages.payment_expired("DIBATALKAN"), parse_mode=ParseMode.HTML
            )
            return


def register(application: Application) -> None:
    """Register command, callback, and text handlers."""
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", handle_admin_menu))
    application.add_handler(CallbackQueryHandler(callback_router))
    application.add_handler(MessageHandler(filters.PHOTO, media_router))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, text_router)
    )


def setup_bot_data(
    application: Application, pakasir_client: PakasirClient, telemetry: TelemetryTracker
) -> None:
    """Populate application.bot_data with shared services."""
    application.bot_data["cart_manager"] = CartManager()
    application.bot_data["telemetry"] = telemetry
    application.bot_data["pakasir_client"] = pakasir_client
    application.bot_data["payment_service"] = PaymentService(
        pakasir_client=pakasir_client,
        telemetry=telemetry,
    )
    application.bot_data["anti_spam"] = AntiSpamGuard()
    application.bot_data["refund_calculator_config"] = load_config()
    # Inisialisasi CustomConfigManager untuk admin config
    try:
        config_adapter = PostgresConfigAdapter()
        application.bot_data["custom_config_mgr"] = CustomConfigManager(config_adapter)
        logger.info("CustomConfigManager terhubung ke Postgres.")
    except Exception as exc:  # pragma: no cover - fallback path
        logger.exception("Gagal menginisialisasi PostgresConfigAdapter: %s", exc)
        application.bot_data["custom_config_mgr"] = CustomConfigManager(
            DummyDBAdapter()
        )
    # Set admin_ids dari konfigurasi
    settings = get_settings()
    application.bot_data["admin_ids"] = [
        str(i) for i in (settings.telegram_admin_ids or [])
    ]
    application.bot_data["owner_ids"] = [
        str(i) for i in (settings.telegram_owner_ids or [])
    ]
    if application.job_queue:
        application.job_queue.run_repeating(
            process_pending_snk_notifications,
            interval=60,
            first=10,
            name="snk_notifier",
        )
        application.job_queue.run_repeating(
            process_broadcast_queue,
            interval=10,
            first=5,
            name="broadcast_dispatcher",
        )
        application.job_queue.run_repeating(
            purge_snk_submissions_job,
            interval=24 * 3600,
            first=60,
            name="snk_purge",
        )


async def _check_spam(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    alert_callback: bool = False,
) -> bool:
    user = update.effective_user
    if user is None:
        return False
    try:
        if await is_user_blocked(telegram_id=user.id):
            message = update.effective_message
            if message:
                await message.reply_text(
                    "❌ Akun kamu sedang diblokir oleh admin. Hubungi admin untuk bantuan."
                )
            return True
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Gagal mengecek status blokir user %s: %s", user.id, exc)
    anti_spam = get_anti_spam(context)
    decision = await anti_spam.register_action(user.id)
    if decision.allowed:
        return False

    await _handle_spam(decision, update, context, user, alert_callback=alert_callback)
    return True


# --- Refund Calculator Conversation States ---
(
    REFUND_HARGA,
    REFUND_SISA_HARI,
    REFUND_TOTAL_HARI,
    REFUND_GARANSI,
    REFUND_ORDER_ID,
    REFUND_ORDER_DATE,
    REFUND_INVOICE_ID,
) = range(7)


async def refund_calculator_start(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    await update.message.reply_text(
        "🧮 Kalkulator Refund\n\nMasukkan harga langganan (contoh: 10000):"
    )
    return REFUND_HARGA


async def refund_calculator_harga(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    try:
        harga = float(update.message.text.strip())
        context.user_data["refund_harga"] = harga
        await update.message.reply_text("Masukkan sisa hari langganan (contoh: 15):")
        return REFUND_SISA_HARI
    except Exception:
        await update.message.reply_text(
            "Format harga tidak valid. Masukkan angka saja."
        )
        return REFUND_HARGA


async def refund_calculator_sisa_hari(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    try:
        sisa_hari = int(update.message.text.strip())
        context.user_data["refund_sisa_hari"] = sisa_hari
        await update.message.reply_text("Masukkan total hari langganan (contoh: 30):")
        return REFUND_TOTAL_HARI
    except Exception:
        await update.message.reply_text(
            "Format sisa hari tidak valid. Masukkan angka saja."
        )
        return REFUND_SISA_HARI


async def refund_calculator_total_hari(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    try:
        total_hari = int(update.message.text.strip())
        context.user_data["refund_total_hari"] = total_hari
        await update.message.reply_text("Berapa kali sudah claim garansi? (contoh: 0):")
        return REFUND_GARANSI
    except Exception:
        await update.message.reply_text(
            "Format total hari tidak valid. Masukkan angka saja."
        )
        return REFUND_TOTAL_HARI


async def refund_calculator_garansi(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    try:
        garansi_claims = int(update.message.text.strip())
        context.user_data["refund_garansi_claims"] = garansi_claims
        await update.message.reply_text("Masukkan order_id (boleh dikosongkan):")
        return REFUND_ORDER_ID
    except Exception:
        await update.message.reply_text(
            "Format jumlah claim garansi tidak valid. Masukkan angka saja."
        )
        return REFUND_GARANSI


async def refund_calculator_order_id(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    order_id = update.message.text.strip()
    context.user_data["refund_order_id"] = order_id
    await update.message.reply_text(
        "Masukkan order_date (YYYY-MM-DD, boleh dikosongkan):"
    )
    return REFUND_ORDER_DATE


async def refund_calculator_order_date(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    order_date = update.message.text.strip()
    context.user_data["refund_order_date"] = order_date
    await update.message.reply_text("Masukkan invoice_id (boleh dikosongkan):")
    return REFUND_INVOICE_ID


async def refund_calculator_invoice_id(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    invoice_id = update.message.text.strip()
    user_id = update.effective_user.id if update.effective_user else None
    harga = context.user_data.get("refund_harga")
    sisa_hari = context.user_data.get("refund_sisa_hari")
    total_hari = context.user_data.get("refund_total_hari")
    garansi_claims = context.user_data.get("refund_garansi_claims", 0)
    order_id = context.user_data.get("refund_order_id", "")
    order_date = context.user_data.get("refund_order_date", "")
    result = calculate_refund(harga, sisa_hari, total_hari, garansi_claims)
    add_history(
        order_id=order_id,
        order_date=order_date,
        invoice_id=invoice_id,
        input_data={
            "harga": harga,
            "sisa_hari": sisa_hari,
            "total_hari": total_hari,
            "garansi_claims": garansi_claims,
        },
        result=result,
        user_id=user_id,
    )
    reply = (
        f"🧮 Hasil Kalkulasi Refund:\n"
        f"Harga: Rp {harga:,.2f}\n"
        f"Sisa Hari: {sisa_hari}\n"
        f"Total Hari: {total_hari}\n"
        f"Claim Garansi: {garansi_claims}\n"
        f"Fee: {result['fee']}\n"
        f"Formula: {result['formula']}\n"
        f"Refund: Rp {result['refund']:,.2f}\n"
        f"Catatan: {result['notes']}\n"
        f"\nOrder ID: {order_id}\nOrder Date: {order_date}\nInvoice ID: {invoice_id}\n"
        f"\nHistory tersimpan. Untuk cek history, admin bisa gunakan /refund_history."
    )
    await update.message.reply_text(reply)
    return ConversationHandler.END


async def refund_calculator_cancel(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    await update.message.reply_text("Kalkulator refund dibatalkan.")
    return ConversationHandler.END


# --- Admin: Set Calculator Config ---
async def set_calculator_start(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    user_id = update.effective_user.id if update.effective_user else None
    settings = get_settings()
    admin_ids = settings.telegram_admin_ids or []
    if user_id not in admin_ids:
        await update.message.reply_text(
            "❌ Hanya admin yang bisa mengubah konfigurasi kalkulator refund."
        )
        return ConversationHandler.END
    await update.message.reply_text(
        "🛠️ Custom Kalkulator Refund\n"
        "Kirim JSON config baru untuk kalkulator refund.\n"
        "Contoh:\n"
        "{\n"
        '  "refund_formula": "(harga * sisa_hari / total_hari) * fee",\n'
        '  "fee_rules": [ ... ],\n'
        '  "notes": "Penjelasan ..."\n'
        "}\n"
        "Kirim di satu pesan."
    )
    return 0


async def set_calculator_config(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    user_id = update.effective_user.id if update.effective_user else None
    settings = get_settings()
    admin_ids = settings.telegram_admin_ids or []
    if user_id not in admin_ids:
        await update.message.reply_text(
            "❌ Hanya admin yang bisa mengubah konfigurasi kalkulator refund."
        )
        return ConversationHandler.END
    try:
        new_config = json.loads(update.message.text)
        update_config(new_config)
        await update.message.reply_text(
            "✅ Konfigurasi kalkulator refund berhasil diupdate."
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Gagal update config: {e}")
    return ConversationHandler.END


# --- Admin: Refund History ---
async def refund_history_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    user_id = update.effective_user.id if update.effective_user else None
    settings = get_settings()
    admin_ids = settings.telegram_admin_ids or []
    if user_id not in admin_ids:
        await update.message.reply_text(
            "❌ Hanya admin yang bisa melihat history kalkulator refund."
        )
        return
    args = context.args
    order_id = args[0] if args else None
    history = get_history(order_id=order_id)
    if not history:
        await update.message.reply_text(
            "Tidak ada history refund untuk order_id tersebut."
        )
        return
    reply = "📜 Refund History:\n"
    for entry in history[-10:]:
        reply += (
            f"- Order ID: {entry.get('order_id')}\n"
            f"  Invoice ID: {entry.get('invoice_id')}\n"
            f"  Date: {entry.get('order_date')}\n"
            f"  Refund: Rp {entry['result']['refund']:,.2f}\n"
            f"  Input: {entry['input']}\n"
            f"  Time: {entry.get('timestamp')}\n"
        )
    await update.message.reply_text(reply)


def register_admin_handlers(application: Application) -> None:
    """Register command, callback, and text handlers."""
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(callback_router))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, text_router)
    )
    # Refund calculator conversation
    refund_calc_conv = ConversationHandler(
        entry_points=[CommandHandler("refund_calculator", refund_calculator_start)],
        states={
            REFUND_HARGA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, refund_calculator_harga)
            ],
            REFUND_SISA_HARI: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, refund_calculator_sisa_hari
                )
            ],
            REFUND_TOTAL_HARI: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, refund_calculator_total_hari
                )
            ],
            REFUND_GARANSI: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, refund_calculator_garansi
                )
            ],
            REFUND_ORDER_ID: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, refund_calculator_order_id
                )
            ],
            REFUND_ORDER_DATE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, refund_calculator_order_date
                )
            ],
            REFUND_INVOICE_ID: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, refund_calculator_invoice_id
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", refund_calculator_cancel)],
    )
    application.add_handler(refund_calc_conv)
    # Set calculator config (admin only)
    set_calc_conv = ConversationHandler(
        entry_points=[CommandHandler("set_calculator", set_calculator_start)],
        states={
            0: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_calculator_config)],
        },
        fallbacks=[],
    )
    application.add_handler(set_calc_conv)
    # Refund history (admin only)
    application.add_handler(CommandHandler("refund_history", refund_history_command))


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
