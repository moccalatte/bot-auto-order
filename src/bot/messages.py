"""Message templates enriched with emoji and casual-baku tone."""

from __future__ import annotations

from datetime import datetime

from src.services.catalog import Product

EMOJI_SEPARATOR = "--------------------------------"


def welcome_message(
    *,
    mention: str,
    store_name: str,
    total_users: int,
    total_transactions: int,
) -> str:
    """Welcome text for /start command."""
    return (
        f"🌟 Hai, **{mention}**! 👋🏻\n\n"
        f"🎪 Selamat datang di **{store_name}** 🎉\n"
        f"🙍🏻‍♂️ Total Sahabat Bot: {total_users:,} orang\n"
        f"💼 Transaksi Tuntas: {total_transactions:,}x\n\n"
        "🛒 Silakan pakai tombol di bawah untuk jelajahi katalog kami!"
    )


def product_list_heading(title: str) -> str:
    """Return heading for product list message."""
    return f"🧾 Daftar {title}\n{EMOJI_SEPARATOR}"


def product_list_line(index: int, product: Product) -> str:
    """Render single product line for list message."""
    description = product.description or "Tidak ada deskripsi untuk produk ini"
    category_label = product.category.name if product.category else "Uncategory"
    category_emoji = product.category.emoji if product.category else "📦"
    return (
        f"{index}. {product.name} = {product.formatted_price}\n"
        f"📝 {description}\n"
        f"📦 Stok ➜ x{product.stock}\n"
        f"🔥 Terjual ➜ {product.sold_count}x\n"
        f"{category_emoji} Kategori ➜ {category_label}\n"
        f"{EMOJI_SEPARATOR}"
    )


def product_detail(product: Product, quantity: int = 0) -> str:
    """Build product detail message body."""
    description = product.description or "Tidak ada deskripsi untuk produk ini"
    category_label = product.category.name if product.category else "Uncategory"
    category_emoji = product.category.emoji if product.category else "📦"
    base_lines = [
        f"⌊ {product.name} ⌉",
        f"🗒️ {description}",
        "",
        f"💲 Harga: {product.formatted_price}",
        f"📦 Stok Tersedia: {product.stock}x",
        f"{category_emoji} Category: {category_label}",
    ]

    if quantity > 0:
        total_cents = product.price_cents * quantity
        total_rp = f"Rp {total_cents / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        base_lines.extend(
            [
                "",
                f"🛍️ In Cart: {quantity}x",
                f"💰 Total Dibayar: {total_rp}",
            ]
        )

    base_lines.extend(
        [
            "",
            "➕ Tekan tombol untuk menambahkan item ke keranjang dan lanjut checkout.",
        ]
    )
    return "\n".join(base_lines)


def cart_summary(cart_lines: list[str], total_items: int, total_rp: str) -> str:
    """Generate cart summary block."""
    body = "\n".join(cart_lines) if cart_lines else "Keranjangmu masih kosong."
    return (
        "⛺ Keranjang Belanja Kamu\n"
        "✅ Pastikan jumlah item dan harga sudah pas ya.\n"
        f"{EMOJI_SEPARATOR}\n"
        f"📦 Total Item: {total_items}\n"
        f"💵 Total Dibayar: {total_rp}\n\n"
        f"{body}\n\n"
        "🚫 Kami tidak menerima komplain setelah pembayaran selesai."
    )


def payment_prompt(total_rp: str, user_name: str, balance_rp: str, bank_id: str | None) -> str:
    """Prompt user to choose payment method."""
    lines = [
        "🧊 Silakan Pilih Metode Pembayaran",
        "",
        "💳 Informasi Tagihan",
        f"— Total Dibayar: {total_rp}",
        f"- Date Created: {datetime.now().strftime('%d/%m/%y')}",
        "",
        "🙋 Informasi Kamu",
        f"— Name: {user_name}",
        f"— Saldo Kamu: {balance_rp}",
        f"— Bank Id: {bank_id or '-'}",
        "— Status Akun: Aktif ✅",
    ]
    return "\n".join(lines)


def payment_loading() -> str:
    """Message shown while invoice is being prepared."""
    return "🎲 Sedang memuat pembayaranmu, harap tunggu sebentar ya..."


def payment_invoice_detail(
    *,
    invoice_id: str,
    items: list[str],
    total_rp: str,
    expires_in: str,
    created_at: str,
) -> str:
    """Formatted invoice summary text."""
    items_block = "\n".join(items)
    return (
        f"🏷️ Invoice Berhasil Dibuat\n{invoice_id}\n\n"
        "🛍️ Informasi Item:\n"
        f"— Total Harga: {total_rp}\n"
        f"— Jumlah Item: {len(items)}x\n"
        f"— List Yang Dibeli:\n{items_block}\n\n"
        "💰 Informasi Pembayaran:\n"
        f"— ID Transaksi: {invoice_id}\n"
        f"— Tanggal Dibuat: {created_at}\n"
        f"— Total Dibayar: {total_rp}\n"
        f"— Expired In: {expires_in}\n"
    )


def payment_expired(invoice_id: str) -> str:
    """Notify that invoice has expired."""
    return (
        f"📜 Tagihan Kadaluarsa\n{invoice_id}\n\n"
        "⚠️ Tagihan kamu sudah tidak aktif.\n"
        "🔁 Silakan ulangi pembelian untuk mendapatkan tagihan QRIS baru.\n"
        "💬 Kalau butuh bantuan, hubungi admin ya!"
    )


def payment_success(product_lines: list[str]) -> str:
    """Message shown after successful payment."""
    return (
        "🎉 Pembayaran Berhasil!\n"
        "✨ Terima kasih sudah belanja di toko kami.\n\n"
        "📦 Detail Produk:\n"
        f"{EMOJI_SEPARATOR}\n"
        f"{chr(10).join(product_lines)}\n\n"
        "📄 S&K berlaku ya. Selamat menikmati layanan! 😄"
    )


def generic_error() -> str:
    """Fallback error message."""
    return (
        "⚠️ Aduh, sistem lagi sibuk nih.\n"
        "💡 Silakan coba lagi dalam beberapa saat atau kontak admin ya.\n"
        "🙏 Terima kasih sudah sabar menunggu."
    )
