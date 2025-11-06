"""Business logic helpers for admin menu actions."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

from telegram import Update
from telegram.ext import ContextTypes

from src.core.audit import audit_log
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
from src.services.order import (
    list_orders,
    update_order_status,
    ensure_order_can_transition,
)
from src.services.users import block_user, list_users, unblock_user
from src.services.voucher import add_voucher, delete_voucher, list_vouchers
from src.services.terms import set_product_terms, clear_product_terms
from src.services.owner_alerts import notify_owners
from src.bot.admin.messages import AdminMessages

logger = logging.getLogger(__name__)


class AdminActionError(Exception):
    """Raised when admin action parsing or execution fails."""


def _parse_int(value: str, field: str) -> int:
    try:
        return int(value)
    except (ValueError, TypeError) as exc:
        raise AdminActionError(AdminMessages.VALUE_MUST_BE_NUMBER.format(field=field)) from exc


def parse_price_to_cents(value: str) -> int:
    """Convert price string to cents. Public function for use in handlers."""
    normalised = value.replace(".", "").replace(",", ".")
    try:
        rupiah = float(normalised)
    except (ValueError, TypeError) as exc:
        raise AdminActionError(AdminMessages.PRICE_INVALID) from exc
    return int(round(rupiah * 100))


def _parse_price_to_cents(value: str) -> int:
    """Deprecated: Use parse_price_to_cents instead."""
    return parse_price_to_cents(value)


def _parse_voucher_id(raw: str) -> int:
    """Parse voucher ID from raw input."""
    return _parse_int(raw.strip(), "voucher_id")


async def handle_add_product_input(
    raw: str,
    actor_id: int,
    *,
    context: ContextTypes.DEFAULT_TYPE | None = None,
) -> str:
    """
    Expected format: category_id|code|name|price|stock|description
    """

    parts = [part.strip() for part in raw.split("|")]
    if len(parts) < 6:
        raise AdminActionError(
            f"{AdminMessages.INVALID_FORMAT} Gunakan: kategori_id|kode|nama|harga|stok|deskripsi."
        )
    category_id = _parse_int(parts[0], "kategori_id")
    code = parts[1]
    name = parts[2]
    price_cents = parse_price_to_cents(parts[3])
    stock = _parse_int(parts[4], "stok")
    description = parts[5]

    product_id = await add_product(
        category_id=category_id,
        code=code,
        name=name,
        description=description,
        price_cents=price_cents,
        stock=stock,
    )
    if context is not None:
        context.user_data["pending_snk_product"] = {
            "product_id": product_id,
            "product_name": name,
        }

    logger.info("Admin %s menambahkan produk baru %s (%s).", actor_id, name, code)
    audit_log(
        actor_id=actor_id,
        action="admin.product.add",
        details={
            "product_id": product_id,
            "code": code,
            "name": name,
            "category_id": category_id,
            "price_cents": price_cents,
            "stock": stock,
        },
    )
    return AdminMessages.PRODUCT_ADDED.format(name=name)


async def _load_product(product_id: int) -> Product:
    product = await get_product(product_id)
    if product is None:
        raise AdminActionError("Produk tidak ditemukan.")
    return product


async def save_product_snk(product_id: int, content: str, actor_id: int) -> str:
    """Save SNK content for product."""
    product = await _load_product(product_id)
    await set_product_terms(product_id=product_id, content=content)
    audit_log(
        actor_id=actor_id,
        action="admin.product.snk.save",
        details={"product_id": product_id},
    )
    logger.info(
        "Admin %s menyimpan SNK untuk produk %s (%s).",
        actor_id,
        product_id,
        product.name,
    )
    await notify_owners(
        f"✏️ SNK produk '{product.name}' diperbarui oleh admin {actor_id}."
    )
    return AdminMessages.SNK_SAVED.format(name=product.name)


async def clear_product_snk(product_id: int, actor_id: int) -> str:
    """Delete SNK for product."""
    product = await _load_product(product_id)
    await clear_product_terms(product_id)
    audit_log(
        actor_id=actor_id,
        action="admin.product.snk.clear",
        details={"product_id": product_id},
    )
    logger.info(
        "Admin %s menghapus SNK untuk produk %s (%s).",
        actor_id,
        product_id,
        product.name,
    )
    await notify_owners(
        f"🧹 SNK produk '{product.name}' dihapus oleh admin {actor_id}."
    )
    return AdminMessages.SNK_CLEARED.format(name=product.name)


async def handle_manage_product_snk_input(raw: str, actor_id: int) -> str:
    """
    Expected format: product_id|SNK baru
    Gunakan kata kunci 'hapus' untuk menghapus SNK.
    """

    parts = [part.strip() for part in raw.split("|", maxsplit=1)]
    if len(parts) != 2:
        raise AdminActionError(
            f"{AdminMessages.INVALID_FORMAT} Gunakan: product_id|SNK baru atau product_id|hapus."
        )
    product_id = _parse_int(parts[0], "product_id")
    payload = parts[1]
    if payload.lower() in {"hapus", "delete", "remove"}:
        return await clear_product_snk(product_id, actor_id)
    if not payload:
        raise AdminActionError("SNK tidak boleh kosong.")
    return await save_product_snk(product_id, payload, actor_id)


async def handle_edit_product_input(raw: str, actor_id: int) -> str:
    """
    Expected format: product_id|field=value,field=value
    Allowed fields: name, description, price, stock, code, category_id
    """

    parts = [part.strip() for part in raw.split("|", maxsplit=1)]
    if len(parts) != 2:
        raise AdminActionError(
            f"{AdminMessages.INVALID_FORMAT} Gunakan: produk_id|field=value,field=value."
        )
    product_id = _parse_int(parts[0], "produk_id")
    updates: Dict[str, Any] = {}
    for assignment in parts[1].split(","):
        if "=" not in assignment:
            raise AdminActionError(f"{AdminMessages.INVALID_FORMAT} {assignment}")
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
    audit_log(
        actor_id=actor_id,
        action="admin.product.edit",
        details={"product_id": product_id, "fields": updates},
    )
    return AdminMessages.PRODUCT_UPDATED.format(product_id=product_id)


async def handle_delete_product_input(raw: str, actor_id: int) -> str:
    product_id = _parse_int(raw.strip(), "produk_id")
    product = await get_product(product_id)
    if product is None:
        raise AdminActionError("Produk tidak ditemukan.")
    await delete_product(product_id)
    logger.info("Admin %s menghapus produk %s.", actor_id, product_id)
    audit_log(
        actor_id=actor_id,
        action="admin.product.delete",
        details={"product_id": product_id, "name": product.name},
    )
    return AdminMessages.PRODUCT_DELETED.format(name=product.name)


async def handle_update_order_input(raw: str, actor_id: int) -> str:
    parts = [part.strip() for part in raw.split("|")]
    if len(parts) < 2:
        raise AdminActionError(
            f"{AdminMessages.INVALID_FORMAT} Gunakan: order_id|status_baru|catatan(optional)."
        )

    order_id_str, new_status = parts[0], parts[1]
    note = parts[2] if len(parts) >= 3 else ""

    if not order_id_str:
        raise AdminActionError("Order ID tidak boleh kosong.")
    if not new_status:
        raise AdminActionError("Status baru tidak boleh kosong.")

    order_id = _parse_int(order_id_str, "order_id")
    try:
        await ensure_order_can_transition(
            order_id,
            new_status,
            admin_id=actor_id,
            note=note or None,
        )
    except ValueError as exc:  # convert to admin-facing error
        raise AdminActionError(str(exc)) from exc

    await update_order_status(order_id, new_status)
    logger.info(
        "Admin %s mengubah status order %s menjadi %s (catatan=%s).",
        actor_id,
        order_id,
        new_status,
        note or "-",
    )
    if note:
        audit_log(
            actor_id=actor_id,
            action="admin.order.update_manual",
            details={
                "order_id": order_id,
                "status": new_status,
                "note": note,
            },
        )
        return AdminMessages.ORDER_UPDATED_WITH_NOTE.format(
            order_id=order_id, new_status=new_status
        )

    audit_log(
        actor_id=actor_id,
        action="admin.order.update",
        details={"order_id": order_id, "status": new_status},
    )
    return AdminMessages.ORDER_UPDATED.format(order_id=order_id, new_status=new_status)


async def handle_block_user_input(
    raw: str, actor_id: int, *, unblock: bool = False
) -> str:
    user_id = _parse_int(raw.strip(), "user_id")
    if unblock:
        await unblock_user(user_id)
        logger.info("Admin %s melakukan unblock pada user %s.", actor_id, user_id)
        audit_log(
            actor_id=actor_id,
            action="admin.user.unblock",
            details={"user_id": user_id},
        )
        return AdminMessages.USER_UNBLOCKED.format(user_id=user_id)
    await block_user(user_id)
    logger.info("Admin %s memblokir user %s.", actor_id, user_id)
    audit_log(
        actor_id=actor_id,
        action="admin.user.block",
        details={"user_id": user_id},
    )
    return AdminMessages.USER_BLOCKED.format(user_id=user_id)


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
        order_id = order["id"]
        lines.append(f"<b>{order_id}</b>\n{total} • {status} • {username}")
    return "📋 <b>Daftar Order Terbaru:</b>\n" + "\n".join(lines)


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


async def render_voucher_overview(limit: int = 20) -> str:
    vouchers = await list_vouchers(limit=limit)
    if not vouchers:
        return "🎟️ Tidak ada voucher aktif."
    lines: List[str] = []
    for voucher in vouchers:
        code = voucher.get("code")
        discount_type = voucher.get("discount_type")
        value = voucher.get("discount_value")
        max_uses = voucher.get("max_uses") or "-"
        valid_from = voucher.get("valid_from")
        valid_until = voucher.get("valid_until")

        def _fmt(ts):
            if isinstance(ts, datetime):
                return ts.strftime("%d/%m/%Y %H:%M")
            return ts or "-"

        lines.append(
            f"{code} • {discount_type} {value} • Max {max_uses} • {_fmt(valid_from)} → {_fmt(valid_until)}"
        )
    return "🎟️ Voucher Aktif:\n" + "\n".join(lines)


def _parse_optional_datetime(value: str) -> datetime | None:
    value = value.strip()
    if not value or value == "-":
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise AdminActionError(f"Format tanggal tidak dikenali: {value}")


async def handle_generate_voucher_input(raw: str, actor_id: int) -> str:
    """
    Format sederhana: KODE | NOMINAL | BATAS_PAKAI

    Contoh:
    - HEMAT10 | 10% | 100  -> diskon 10% max 100 kali pakai
    - DISKON5K | 5000 | 50 -> diskon Rp 5.000 max 50 kali pakai
    """

    parts = [part.strip() for part in raw.split("|")]
    if len(parts) != 3:
        raise AdminActionError(
            f"{AdminMessages.INVALID_FORMAT} Gunakan: KODE | NOMINAL | BATAS_PAKAI\n"
            "Contoh: HEMAT10 | 10% | 100"
        )

    code = parts[0].upper()  # Force uppercase untuk konsistensi
    nominal_str = parts[1]
    max_uses_str = parts[2]

    # Parse nominal - bisa berupa persen (10%) atau nilai rupiah (5000)
    if nominal_str.endswith("%"):
        discount_type = "percent"  # Database constraint uses 'percent'
        discount_value = _parse_int(nominal_str[:-1], "persen")
        if not 1 <= discount_value <= 100:
            raise AdminActionError("Persen harus antara 1-100")
    else:
        discount_type = "flat"  # Database constraint uses 'flat'
        discount_value = _parse_int(nominal_str, "nominal")
        if discount_value <= 0:
            raise AdminActionError("Nominal harus lebih dari 0")

    # Parse max uses
    max_uses = _parse_int(max_uses_str, "batas pakai")
    if max_uses <= 0:
        raise AdminActionError("Batas pakai harus lebih dari 0")

    # Create voucher dengan deskripsi otomatis
    if discount_type == "percent":
        description = f"Diskon {discount_value}%"
    else:
        description = f"Diskon Rp {discount_value:,}".replace(",", ".")

    voucher_id = await add_voucher(
        code=code,
        description=description,
        discount_type=discount_type,
        discount_value=discount_value,
        max_uses=max_uses,
        valid_from=None,  # Langsung aktif
        valid_until=None,  # Tidak ada expired
    )

    logger.info(
        "Admin %s membuat voucher %s (id=%s) tipe=%s nilai=%s max_uses=%s",
        actor_id,
        code,
        voucher_id,
        discount_type,
        discount_value,
        max_uses,
    )
    audit_log(
        actor_id=actor_id,
        action="admin.voucher.create",
        details={
            "voucher_id": voucher_id,
            "code": code,
            "discount_type": discount_type,
            "discount_value": discount_value,
            "max_uses": max_uses,
        },
    )

    return AdminMessages.VOUCHER_CREATED.format(
        code=code,
        description=description,
        max_uses=max_uses,
        voucher_id=voucher_id,
    )


async def handle_delete_voucher_input(raw: str, actor_id: int) -> str:
    voucher_id = _parse_voucher_id(raw)
    await delete_voucher(voucher_id)
    logger.info("Admin %s menonaktifkan voucher id=%s.", actor_id, voucher_id)
    audit_log(
        actor_id=actor_id,
        action="admin.voucher.disable",
        details={"voucher_id": voucher_id},
    )
    return AdminMessages.VOUCHER_DISABLED.format(voucher_id=voucher_id)


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
    "render_voucher_overview",
    "list_categories_overview",
    "handle_generate_voucher_input",
    "handle_delete_voucher_input",
    "save_product_snk",
    "clear_product_snk",
    "handle_manage_product_snk_input",
]
