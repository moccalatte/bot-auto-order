"""Admin menu & customization handler for Telegram bot (custom_plan.md)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import ContextTypes


# Placeholder for database/model integration
def get_admin_config(user_id: int) -> Dict[str, Any]:
    """Fetch admin config from database."""
    # TODO: Integrate with actual DB
    return {
        "responses": {
            "order_created": "🎉 Order {order_id} atas nama {nama} telah diterima!",
            "payment_success": "✅ Pembayaran untuk order {order_id} sukses.",
        }
    }


def save_admin_config(user_id: int, config: Dict[str, Any]) -> None:
    """Save admin config to database."""
    # TODO: Integrate with actual DB
    pass


def admin_main_menu() -> ReplyKeyboardMarkup:
    """Menu utama admin: ⚙️ Admin Settings (hanya untuk admin)."""
    keyboard = [
        ["🛠 Kelola Respon Bot"],
        ["🛒 Kelola Produk"],
        ["📦 Kelola Order"],
        ["👥 Kelola User"],
        ["⬅️ Kembali ke Menu Utama"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def admin_response_menu() -> InlineKeyboardMarkup:
    """Menu untuk kustomisasi respon bot."""
    buttons = [
        [
            InlineKeyboardButton(
                "👁️ Preview Semua Respon", callback_data="admin:preview_responses"
            )
        ],
        [InlineKeyboardButton("⬅️ Kembali", callback_data="admin:back")],
    ]
    return InlineKeyboardMarkup(buttons)


def admin_product_menu() -> InlineKeyboardMarkup:
    """Menu CRUD produk."""
    buttons = [
        [InlineKeyboardButton("➕ Tambah Produk", callback_data="admin:add_product")],
        [InlineKeyboardButton("📝 Edit Produk", callback_data="admin:edit_product")],
        [InlineKeyboardButton("🗑️ Hapus Produk", callback_data="admin:delete_product")],
        [InlineKeyboardButton("⬅️ Kembali", callback_data="admin:back")],
    ]
    return InlineKeyboardMarkup(buttons)


def admin_order_menu() -> InlineKeyboardMarkup:
    """Menu kelola order."""
    buttons = [
        [
            InlineKeyboardButton(
                "📋 Lihat Daftar Order", callback_data="admin:list_orders"
            )
        ],
        [
            InlineKeyboardButton(
                "🔄 Update Status Order", callback_data="admin:update_order"
            )
        ],
        [InlineKeyboardButton("⬅️ Kembali", callback_data="admin:back")],
    ]
    return InlineKeyboardMarkup(buttons)


def admin_user_menu() -> InlineKeyboardMarkup:
    """Menu kelola user."""
    buttons = [
        [InlineKeyboardButton("👥 Lihat User", callback_data="admin:list_users")],
        [InlineKeyboardButton("🚫 Blokir User", callback_data="admin:block_user")],
        [InlineKeyboardButton("✅ Unblokir User", callback_data="admin:unblock_user")],
        [InlineKeyboardButton("⬅️ Kembali", callback_data="admin:back")],
    ]
    return InlineKeyboardMarkup(buttons)


async def handle_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Entry point for admin menu."""
    user = update.effective_user
    if not user or not str(user.id) in context.bot_data.get("admin_ids", []):
        await update.message.reply_text("❌ Kamu tidak punya akses admin.")
        return

    # Tampilkan menu utama admin
    # Hanya admin yang bisa melihat menu ini
    admin_ids = context.bot_data.get("admin_ids", [])
    if str(user.id) not in admin_ids:
        await update.message.reply_text("❌ Kamu tidak punya akses admin.")
        return

    await update.message.reply_text(
        "⚙️ Admin Settings:\nSilakan pilih aksi di bawah.",
        reply_markup=admin_main_menu(),
    )


# Handler detail diatur di src/bot/admin/admin_actions.py & handlers.py.
