bot - auto - order / src / bot / admin / admin_menu.py  # L1-98
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
    """Build main admin menu keyboard."""
    keyboard = [
        ["🛠 Kelola Respon Bot", "🛒 Kelola Produk"],
        ["📦 Kelola Order", "👥 Kelola User"],
        ["⬅️ Kembali ke Menu Utama"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def admin_response_menu() -> InlineKeyboardMarkup:
    """Menu untuk kustomisasi respon bot."""
    buttons = [
        [
            InlineKeyboardButton(
                "✏️ Edit Template Order Masuk",
                callback_data="admin:edit_response:order_created",
            )
        ],
        [
            InlineKeyboardButton(
                "✏️ Edit Template Pembayaran",
                callback_data="admin:edit_response:payment_success",
            )
        ],
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
        [InlineKeyboardButton("🖼️ Upload Gambar", callback_data="admin:upload_image")],
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

    # Cek apakah admin mengirim template pesan baru
    last_command = context.user_data.get("admin_last_command")
    config_mgr = context.bot_data.get("custom_config_mgr")
    if last_command and config_mgr:
        try:
            # Validasi dan simpan template pesan
            await config_mgr.set_config(last_command, update.message.text)
            await update.message.reply_text(
                f"✅ Template pesan '{last_command}' berhasil diupdate dan divalidasi."
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Gagal update template: {e}")
        context.user_data["admin_last_command"] = None
        return

    # Tampilkan menu utama admin
    await update.message.reply_text(
        "⚙️ Menu Admin:\nSilakan pilih aksi di bawah.",
        reply_markup=admin_main_menu(),
    )


# TODO: Implement handlers for each submenu and config change, with DB integration, validation, preview, backup/restore, and logging.
