"""Keyboard factories with emoji-rich buttons."""

from __future__ import annotations

from typing import Iterable, List, Sequence

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

from src.services.catalog import Category, Product


def main_reply_keyboard(product_numbers: Sequence[int]) -> ReplyKeyboardMarkup:
    """Build main reply keyboard with emoji entries."""
    numbers_row = [f"{index}️⃣" for index in product_numbers]
    keyboard = [
        ["📋 List Produk", "🛍 Semua Produk"],
        ["🏷 Cek Stok", "💰 Deposit"],
        numbers_row,
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def category_inline_keyboard(categories: Iterable[Category]) -> InlineKeyboardMarkup:
    """Build inline keyboard listing categories and 'All Products'."""
    buttons: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []
    for category in categories:
        row.append(
            InlineKeyboardButton(
                text=f"{category.emoji} {category.name}",
                callback_data=f"category:{category.slug}",
            )
        )
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append(
        [InlineKeyboardButton(text="🧭 Semua Produk", callback_data="category:all")]
    )
    return InlineKeyboardMarkup(buttons)


def product_inline_keyboard(
    product: Product, quantity: int = 0
) -> InlineKeyboardMarkup:
    """Inline keyboard for product detail with quantity controls."""
    buttons = [
        [
            InlineKeyboardButton(text="➖", callback_data=f"cart:remove:{product.id}"),
            InlineKeyboardButton(text="➕", callback_data=f"cart:add:{product.id}"),
        ],
    ]
    if quantity > 0:
        buttons.append(
            [
                InlineKeyboardButton(
                    text="✌️ x2", callback_data=f"cart:set:{product.id}:2"
                ),
                InlineKeyboardButton(
                    text="🖐️ x5", callback_data=f"cart:set:{product.id}:5"
                ),
                InlineKeyboardButton(
                    text="🔟 x10", callback_data=f"cart:set:{product.id}:10"
                ),
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                text="🧺 Lanjut ke Keranjang", callback_data="cart:checkout"
            ),
            InlineKeyboardButton(
                text="❌ Batal", callback_data=f"cart:cancel:{product.id}"
            ),
        ]
    )
    return InlineKeyboardMarkup(buttons)


def cart_inline_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard for cart actions."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text="🎟️ Gunakan Kupon", callback_data="cart:coupon"
                ),
                InlineKeyboardButton(
                    text="💳 Lanjut ke Pembayaran", callback_data="cart:pay"
                ),
            ],
            [InlineKeyboardButton(text="❌ Batal", callback_data="cart:clear")],
        ]
    )


def payment_method_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard presenting payment options."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(text="💠 QRIS", callback_data="pay:qris"),
                InlineKeyboardButton(text="💼 Saldo", callback_data="pay:balance"),
            ],
            [
                InlineKeyboardButton(
                    text="❌ Batalkan Pembelian", callback_data="pay:cancel"
                )
            ],
        ]
    )


def invoice_keyboard(payment_url: str) -> InlineKeyboardMarkup:
    """Inline keyboard for invoice message."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(text="🔗 Checkout URL", url=payment_url)],
            [
                InlineKeyboardButton(
                    text="❌ Batalkan Pembelian", callback_data="pay:cancel"
                )
            ],
        ]
    )


def snk_confirmation_keyboard(notification_id: int) -> InlineKeyboardMarkup:
    """Inline keyboard for SNK confirmation message to customer."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text="✅ Penuhi SNK", callback_data=f"snk:submit:{notification_id}"
                )
            ]
        ]
    )
