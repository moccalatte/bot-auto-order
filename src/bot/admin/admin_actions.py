"""Business logic helpers for admin menu actions."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from telegram import Update
from telegram.ext import ContextTypes

from src.core.currency import format_rupiah
from src.services.catalog import (
    Product,
    add_product,
    delete_product,
    edit_product,
    get_product,
    list_categories,
    list_products,
)
from src.services.order import list_orders, update_order_status
from src.services.users import block_user, list_users, unblock_user

logger = logging.getLogger(__name__)


class AdminActionError(Exception):
    """Raised when admin action parsing or execution fails."""


def _parse_int(value: str, field: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise AdminActionError(f"Nilai '{field}' harus berupa angka.") from exc


def _parse_price_to_cents(value: str) -> int:
    normalised = value.replace(".", "").replace(",", ".")
    try:
        rupiah = float(normalised)
    except ValueError as exc:
        raise AdminActionError(
            "Harga tidak valid. Gunakan format contoh 15000 atau 15000,50."
        ) from exc
    return int(round(rupiah * 100))


async def handle_add_product_input(raw: str, actor_id: int) -> str:
    """
    Expected format: category_id|code|name|price|stock|description
    """

    parts = [part.strip() for part in raw.split("|")]
    if len(parts) < 6:
        raise AdminActionError(
            "Format tidak valid. Gunakan: kategori_id|kode|nama|harga|stok|deskripsi."
        )
    category_id = _parse_int(parts[0], "kategori_id")
    code = parts[1]
    name = parts[2]
    price_cents = _parse_price_to_cents(parts[3])
    stock = _parse_int(parts[4], "stok")
    description = parts[5]

    await add_product(
        category_id=category_id,
        code=code,
        name=name,
        description=description,
        price_cents=price_cents,
        stock=stock,
    )

    logger.info("Admin %s menambahkan produk baru %s (%s).", actor_id, name, code)
    return f"✅ Produk '{name}' berhasil ditambahkan."


async def handle_edit_product_input(raw: str, actor_id: int) -> str:
    """
    Expected format: product_id|field=value,field=value
    Allowed fields: name, description, price, stock, code, category_id
    """

    parts = [part.strip() for part in raw.split("|", maxsplit=1)]
    if len(parts) != 2:
        raise AdminActionError(
            "Format tidak valid. Gunakan: produk_id|field=value,field=value."
        )
    product_id = _parse_int(parts[0], "produk_id")
    updates: Dict[str, Any] = {}
    for assignment in parts[1].split(","):
        if "=" not in assignment:
            raise AdminActionError(f"Format field tidak valid: {assignment}")
        field, value = [item.strip() for item in assignment.split("=", maxsplit=1)]
        if field not in {
            "name",
            "description",
            "price",
            "stock",
            "code",
            "category_id",
        }:
            raise AdminActionError(f"Field '{field}' tidak dikenal.")
        if field == "price":
            updates["price_cents"] = _parse_price_to_cents(value)
        elif field == "stock":
            updates["stock"] = _parse_int(value, "stok")
        elif field == "category_id":
            updates["category_id"] = _parse_int(value, "kategori_id")
        else:
            updates[field] = value

    if not updates:
        raise AdminActionError("Tidak ada field yang diupdate.")

    await edit_product(product_id, **updates)
    logger.info(
        "Admin %s mengubah produk %s: %s", actor_id, product_id, list(updates.keys())
    )
    return f"✅ Produk #{product_id} berhasil diupdate."


async def handle_delete_product_input(raw: str, actor_id: int) -> str:
    product_id = _parse_int(raw.strip(), "produk_id")
    product = await get_product(product_id)
    if product is None:
        raise AdminActionError("Produk tidak ditemukan.")
    await delete_product(product_id)
    logger.info("Admin %s menghapus produk %s.", actor_id, product_id)
    return f"🗑️ Produk '{product.name}' berhasil dihapus."


async def handle_update_order_input(raw: str, actor_id: int) -> str:
    parts = [part.strip() for part in raw.split("|", maxsplit=1)]
    if len(parts) != 2:
        raise AdminActionError("Format tidak valid. Gunakan: order_id|status_baru.")
    order_id, new_status = parts
    if not order_id:
        raise AdminActionError("Order ID tidak boleh kosong.")
    if not new_status:
        raise AdminActionError("Status baru tidak boleh kosong.")
    await update_order_status(order_id, new_status)
    logger.info(
        "Admin %s mengubah status order %s menjadi %s.", actor_id, order_id, new_status
    )
    return f"🔄 Status order {order_id} diupdate ke {new_status}."


async def handle_block_user_input(
    raw: str, actor_id: int, *, unblock: bool = False
) -> str:
    user_id = _parse_int(raw.strip(), "user_id")
    if unblock:
        await unblock_user(user_id)
        logger.info("Admin %s melakukan unblock pada user %s.", actor_id, user_id)
        return f"✅ User #{user_id} berhasil diaktifkan kembali."
    await block_user(user_id)
    logger.info("Admin %s memblokir user %s.", actor_id, user_id)
    return f"🚫 User #{user_id} berhasil diblokir."


def _format_product_line(product: Product) -> str:
    category = product.category.name if product.category else "-"
    price = format_rupiah(product.price_cents)
    return (
        f"#{product.id} {product.name}\n"
        f"• Harga: {price}\n"
        f"• Stok: {product.stock}\n"
        f"• Terjual: {product.sold_count}\n"
        f"• Kategori: {category}"
    )


async def render_product_overview(limit: int = 10) -> str:
    products = await list_products(limit=limit)
    if not products:
        return "📦 Belum ada produk aktif."
    lines = [_format_product_line(product) for product in products]
    return "🛒 Produk Aktif:\n\n" + "\n\n".join(lines)


async def render_order_overview(limit: int = 10) -> str:
    orders = await list_orders(limit=limit)
    if not orders:
        return "📋 Belum ada order."
    lines: List[str] = []
    for order in orders:
        total_cents = int(
            order.get("total_amount_cents") or order.get("total_cents") or 0
        )
        total = format_rupiah(total_cents)
        status = order.get("status", "UNKNOWN")
        username = order.get("username") or order.get("telegram_id") or "-"
        lines.append(f"#{order['id']} • {status} • {total} • {username}")
    return "📋 Daftar Order Terbaru:\n" + "\n".join(lines)


async def render_user_overview(limit: int = 10) -> str:
    users = await list_users(limit=limit)
    if not users:
        return "👥 Belum ada user terdaftar."
    lines = []
    for user in users:
        username = user.get("username") or "-"
        telegram_id = user.get("telegram_id") or "-"
        blocked = "🚫" if user.get("is_blocked") else "✅"
        lines.append(f"#{user['id']} • {username} ({telegram_id}) • {blocked}")
    return "👥 User Terbaru:\n" + "\n".join(lines)


async def list_categories_overview() -> str:
    categories = await list_categories()
    if not categories:
        return "📂 Belum ada kategori aktif."
    lines = [f"#{cat.id} • {cat.emoji} {cat.name} ({cat.slug})" for cat in categories]
    return "📂 Daftar Kategori:\n" + "\n".join(lines)


__all__ = [
    "AdminActionError",
    "handle_add_product_input",
    "handle_edit_product_input",
    "handle_delete_product_input",
    "handle_update_order_input",
    "handle_block_user_input",
    "render_product_overview",
    "render_order_overview",
    "render_user_overview",
    "list_categories_overview",
]
