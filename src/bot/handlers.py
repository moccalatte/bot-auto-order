"""Telegram handlers wiring everything together."""

from __future__ import annotations

import asyncio
import html
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Sequence
from zoneinfo import ZoneInfo

from telegram import (
    CallbackQuery,
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
    handle_add_product_input,
    handle_block_user_input,
    handle_delete_product_input,
    handle_edit_product_input,
    handle_update_order_input,
    handle_generate_voucher_input,
    handle_delete_voucher_input,
    handle_manage_product_snk_input,
    list_categories_overview,
    render_order_overview,
    render_product_overview,
    render_user_overview,
    render_voucher_overview,
    save_product_snk,
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
    get_product,
    list_categories,
    list_products,
    list_products_by_category,
)
from src.services.payment import PaymentError, PaymentService
from src.services.pakasir import PakasirClient
from src.services.stats import get_bot_statistics
from src.services.calculator import (
    load_config,
    save_config,
    calculate_refund,
    add_history,
    get_history,
    update_config,
)
from src.services.users import (
    is_user_blocked,
    list_broadcast_targets,
    mark_user_bot_blocked,
)
from src.services.terms import (
    get_notification,
    list_pending_notifications,
    mark_notification_responded,
    mark_notification_sent,
    record_terms_submission,
)


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


def _store_products(
    context: ContextTypes.DEFAULT_TYPE, products: Sequence[Product]
) -> None:
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
            await context.bot.send_message(
                chat_id=admin_id,
                text=message_text,
                parse_mode=ParseMode.HTML,
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


def _format_broadcast_summary(result: Dict[str, int]) -> str:
    """Build broadcast result summary."""
    return (
        "📣 Broadcast selesai!\n"
        f"👥 Target: {result.get('total', 0)}\n"
        f"✅ Berhasil: {result.get('success', 0)}\n"
        f"🚫 Bot diblokir: {result.get('blocked', 0)}\n"
        f"⚠️ Gagal: {result.get('failed', 0)}"
    )


async def _broadcast_message(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    actor_id: int,
    text: str | None,
    media_file_id: str | None = None,
    media_type: str | None = None,
) -> Dict[str, int]:
    """Send broadcast content to all eligible users."""
    targets = await list_broadcast_targets()
    valid_targets = [
        int(row["telegram_id"]) for row in targets if row.get("telegram_id") is not None
    ]
    stats = {"total": len(valid_targets), "success": 0, "blocked": 0, "failed": 0}
    if not valid_targets:
        logger.info("[broadcast] Tidak ada target broadcast.")
        return stats
    for telegram_id in valid_targets:
        try:
            if media_file_id and media_type == "photo":
                await context.bot.send_photo(
                    chat_id=telegram_id,
                    photo=media_file_id,
                    caption=text or "",
                )
            else:
                await context.bot.send_message(
                    chat_id=telegram_id,
                    text=text or "",
                )
            stats["success"] += 1
        except Forbidden:
            stats["blocked"] += 1
            await mark_user_bot_blocked(telegram_id)
        except TelegramError as exc:  # pragma: no cover - network failure
            stats["failed"] += 1
            logger.error(
                "[broadcast] Gagal mengirim ke %s: %s",
                telegram_id,
                exc,
            )
        await asyncio.sleep(0.05)
    logger.info(
        "[broadcast] Actor %s selesai. total=%s success=%s blocked=%s failed=%s",
        actor_id,
        stats["total"],
        stats["success"],
        stats["blocked"],
        stats["failed"],
    )
    return stats


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


async def process_pending_snk_notifications(
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Background job to deliver SNK messages to customers."""
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
                reply_markup=keyboards.snk_confirmation_keyboard(notification_id),
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

    if is_admin:
        state = get_admin_state(context.user_data)
        if state:
            reply_kwargs: Dict[str, Any] = {}
            keep_state = False
            try:
                if state.action == "add_product":
                    response = await handle_add_product_input(
                        text, user.id, context=context
                    )  # type: ignore[arg-type]
                elif state.action == "add_product_snk_choice":
                    await _handle_add_product_snk_choice(update, context, state, text)
                    return
                elif state.action == "add_product_snk_input":
                    product_id = int(state.payload.get("product_id") or 0)
                    if not product_id:
                        response = "⚠️ Produk untuk SNK tidak ditemukan."
                    else:
                        response = await save_product_snk(product_id, text, user.id)
                    reply_kwargs["reply_markup"] = ReplyKeyboardRemove()
                elif state.action == "broadcast_message":
                    if text.strip().lower() == "batal":
                        response = "🚫 Broadcast dibatalkan."
                    elif not text:
                        response = "⚠️ Pesan broadcast tidak boleh kosong."
                        keep_state = True
                    else:
                        stats = await _broadcast_message(
                            context,
                            actor_id=user.id,
                            text=text,
                        )
                        response = _format_broadcast_summary(stats)
                elif state.action == "manage_product_snk":
                    response = await handle_manage_product_snk_input(text, user.id)  # type: ignore[arg-type]
                elif state.action == "edit_product":
                    response = await handle_edit_product_input(text, user.id)  # type: ignore[arg-type]
                elif state.action == "delete_product":
                    response = await handle_delete_product_input(text, user.id)  # type: ignore[arg-type]
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
                elif state.action == "generate_voucher":
                    response = await handle_generate_voucher_input(text, user.id)  # type: ignore[arg-type]
                elif state.action == "delete_voucher":
                    response = await handle_delete_voucher_input(text, user.id)  # type: ignore[arg-type]
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
            if state.action == "add_product":
                pending = context.user_data.pop("pending_snk_product", None)
                if pending:
                    set_admin_state(
                        context.user_data,
                        "add_product_snk_choice",
                        **pending,
                    )
                    await update.message.reply_text(
                        "Apakah kamu ingin tambahkan SNK untuk produk ini? klik tombol dibawah",
                        reply_markup=ReplyKeyboardMarkup(
                            [["Tambah SNK", "Skip SNK"]],
                            resize_keyboard=True,
                            one_time_keyboard=True,
                        ),
                    )
            return

    # Hapus akses menu produk lama dari admin, hanya gunakan menu settings baru
    if text == "⚙️ Admin Settings":
        if not is_admin:
            await update.message.reply_text("❌ Kamu tidak punya akses admin.")
            return
        from src.bot.admin.admin_menu import admin_main_menu

        await update.message.reply_text(
            "⚙️ Admin Settings:\nSilakan pilih aksi di bawah.",
            reply_markup=admin_main_menu(),
        )
        return
    # Submenu admin settings
    if text == "🛠 Kelola Respon Bot":
        from src.bot.admin.admin_menu import admin_response_menu

        await update.message.reply_text(
            "🛠 Kelola Respon Bot", reply_markup=admin_response_menu()
        )
        return
    if text == "🛒 Kelola Produk":
        from src.bot.admin.admin_menu import admin_product_menu

        await update.message.reply_text(
            "🛒 Kelola Produk", reply_markup=admin_product_menu()
        )
        return
    if text == "📦 Kelola Order":
        from src.bot.admin.admin_menu import admin_order_menu

        await update.message.reply_text(
            "📦 Kelola Order", reply_markup=admin_order_menu()
        )
        return
    if text == "👥 Kelola User":
        from src.bot.admin.admin_menu import admin_user_menu

        await update.message.reply_text(
            "👥 Kelola User", reply_markup=admin_user_menu()
        )
        return
    if text == "🎟️ Kelola Voucher":
        from src.bot.admin.admin_menu import admin_voucher_menu

        await update.message.reply_text(
            "🎟️ Kelola Voucher\nSetiap aksi akan dicatat di log untuk owner.",
            reply_markup=admin_voucher_menu(),
        )
        return
    if text == "⬅️ Kembali ke Admin Settings":
        if not is_admin:
            await update.message.reply_text("❌ Kamu tidak punya akses admin.")
            return
        from src.bot.admin.admin_menu import admin_main_menu

        await update.message.reply_text(
            "⚙️ Admin Settings:\nSilakan pilih aksi di bawah.",
            reply_markup=admin_main_menu(),
        )
        return
    if text == "⬅️ Kembali ke Menu Utama":
        products: Sequence[Product] = context.user_data.get("product_list", [])
        if not products:
            products = await list_products()
        context.user_data["product_list"] = products
        reply_keyboard = keyboards.main_reply_keyboard(range(1, min(len(products), 6)))
        await update.message.reply_text(
            "🏠 Kembali ke menu utama.", reply_markup=reply_keyboard
        )
        return
    if text == "➕ Generate Voucher Baru":
        if not is_admin:
            await update.message.reply_text("❌ Kamu tidak punya akses admin.")
            return
        set_admin_state(context.user_data, "generate_voucher")
        await update.message.reply_text(
            "➕ Format: kode|deskripsi|tipe|nilai|max_uses|valid_from|valid_until\n"
            "Gunakan '-' untuk nilai opsional. Semua perubahan tercatat di log owner."
        )
        return
    if text == "📋 Lihat Voucher Aktif":
        if not is_admin:
            await update.message.reply_text("❌ Kamu tidak punya akses admin.")
            return
        overview = await render_voucher_overview()
        await update.message.reply_text(overview)
        return
    if text == "🗑️ Nonaktifkan/Hapus Voucher":
        if not is_admin:
            await update.message.reply_text("❌ Kamu tidak punya akses admin.")
            return
        set_admin_state(context.user_data, "delete_voucher")
        await update.message.reply_text(
            "🗑️ Kirim ID voucher yang akan dinonaktifkan. Aksi tercatat di log."
        )
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
    if text == "📣 Broadcast Pesan":
        if not is_admin:
            await update.message.reply_text("❌ Kamu tidak punya akses admin.")
            return
        set_admin_state(context.user_data, "broadcast_message")
        await update.message.reply_text(
            "📣 Mode Broadcast Aktif\n"
            "- Kirim teks untuk broadcast ke semua user.\n"
            "- Kirim foto dengan caption untuk broadcast bergambar.\n"
            "Ketik BATAL untuk membatalkan.",
        )
        return

    if text == "💼 Deposit":
        await update.message.reply_text(
            "💼 Menu Deposit\n"
            "🧾 Kamu bisa transfer manual lalu kirim bukti ke admin, atau pilih metode otomatis QRIS di menu pembayaran.\n"
            "🤝 Saldo akan masuk setelah diverifikasi."
        )
        return

    # Handler untuk tombol Calculator
    if text == "🧮 Calculator":
        # Kirim rumus refund dari calcu.md
        try:
            with open("calcu.md", "r") as f:
                calcu_text = f.read()
        except Exception:
            calcu_text = "Rumus refund tidak tersedia. Silakan cek dengan admin atau lihat file calcu.md."
        await update.message.reply_text(
            f"🧮 Kalkulator Refund\n\n{calcu_text}\n\n"
            "Kamu bisa hitung refund dengan rumus di atas.\n"
            "Untuk custom, admin bisa gunakan command /set_calculator.\n"
            "Untuk kalkulasi otomatis, gunakan /refund_calculator."
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

    await update.message.reply_text(messages.generic_error())


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
    user = update.effective_user
    admin_ids = context.bot_data.get("admin_ids", [])
    if user and str(user.id) in admin_ids and message.photo:
        state = get_admin_state(context.user_data)
        if state and state.action == "broadcast_message":
            file_id = message.photo[-1].file_id
            caption = (message.caption or "").strip()
            stats = await _broadcast_message(
                context,
                actor_id=user.id,
                text=caption,
                media_file_id=file_id,
                media_type="photo",
            )
            clear_admin_state(context.user_data)
            await message.reply_text(_format_broadcast_summary(stats))
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

    # --- Admin Menu Callback Integration ---
    # Only allow admin_ids to access admin callbacks
    admin_ids = context.bot_data.get("admin_ids", [])
    if data.startswith("admin:") and str(user.id) in admin_ids:
        from src.bot.admin.admin_menu import (
            admin_response_menu,
            admin_product_menu,
            admin_order_menu,
            admin_user_menu,
            admin_main_menu,
        )

        if data == "admin:back":
            await update.effective_message.reply_text(
                "⚙️ Admin Settings:\nSilakan pilih aksi di bawah.",
                reply_markup=admin_main_menu(),
            )
            return
        elif data == "admin:preview_responses":
            config_mgr = context.bot_data.get("custom_config_mgr")
            order_msg = (
                await config_mgr.get_config("order_created") if config_mgr else None
            )
            payment_msg = (
                await config_mgr.get_config("payment_success") if config_mgr else None
            )
            await update.effective_message.reply_text(
                f"👁️ Preview Respon:\nOrder Masuk: {order_msg}\nPembayaran Sukses: {payment_msg}"
            )
            return
        elif data == "admin:add_product":
            set_admin_state(context.user_data, "add_product")
            categories_text = await list_categories_overview()
            await update.effective_message.reply_text(
                "➕ Format tambah produk:\n"
                "kategori_id|kode|nama|harga|stok|deskripsi\n"
                "Catatan: unggah gambar dikurasi terpisah oleh owner jika diperlukan.\n\n"
                f"{categories_text}"
            )
            return
        elif data == "admin:edit_product":
            set_admin_state(context.user_data, "edit_product")
            await update.effective_message.reply_text(
                "📝 Format edit: produk_id|field=value,field=value\n"
                "Field: name, description, price, stock, code, category_id."
            )
            return
        elif data == "admin:delete_product":
            set_admin_state(context.user_data, "delete_product")
            await update.effective_message.reply_text(
                "🗑️ Kirim ID produk yang ingin dihapus."
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
            await update.effective_message.reply_text(overview)
            return
        elif data == "admin:update_order":
            set_admin_state(context.user_data, "update_order")
            await update.effective_message.reply_text(
                "🔄 Format: order_id|status_baru|catatan(optional). Isi catatan hanya bila pembayaran manual/deposit (misal nomor referensi)."
            )
            return
        elif data == "admin:list_users":
            overview = await render_user_overview()
            await update.effective_message.reply_text(overview)
            return
        elif data == "admin:block_user":
            set_admin_state(context.user_data, "block_user")
            await update.effective_message.reply_text(
                "🚫 Kirim ID user yang ingin diblokir."
            )
            return
        elif data == "admin:unblock_user":
            set_admin_state(context.user_data, "unblock_user", unblock=True)
            await update.effective_message.reply_text(
                "✅ Kirim ID user yang ingin di-unblokir."
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
            await update.effective_message.reply_text(overview)
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
            await _notify_admin_new_order(
                context,
                user,
                cart,
                order_id=str(payload.get("order_id", "")),
                method=action,
                created_at=str(payload.get("created_at")),
            )
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
                    invoice_text
                    + "\n\n(⚠️ QR tidak tersedia, gunakan tautan checkout.)",
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


def register(application: Application) -> None:
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
