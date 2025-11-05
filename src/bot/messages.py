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
        f"🌟 Hai, <b>{mention}</b>! 👋🏻\n\n"
        f"🎪 Selamat datang di <b>{store_name}</b> 🎉\n\n"
        f"📊 <b>Statistik Kami:</b>\n"
        f"🙍🏻‍♂️ Total Pengguna Bot: <b>{total_users:,}</b> orang\n"
        f"💼 Transaksi Tuntas: <b>{total_transactions:,}</b>x\n\n"
        "🛒 Silakan pilih kategori atau gunakan tombol di bawah untuk jelajahi katalog kami!"
    )


def product_list_heading(title: str) -> str:
    """Return heading for product list message."""
    return f"🧾 <b>Daftar {title}</b>\n{EMOJI_SEPARATOR}"


def product_list_line(index: int, product: Product) -> str:
    """Render single product line for list message."""
    description = product.description or "Tidak ada deskripsi untuk produk ini"
    category_label = product.category.name if product.category else "Uncategory"
    category_emoji = product.category.emoji if product.category else "📦"
    return (
        f"{index}. <b>{product.name}</b> = <b>{product.formatted_price}</b>\n"
        f"📝 {description}\n"
        f"📦 Stok ➜ <b>x{product.stock}</b>\n"
        f"🔥 Terjual ➜ <b>{product.sold_count}x</b>\n"
        f"{category_emoji} Kategori ➜ {category_label}\n"
        f"{EMOJI_SEPARATOR}"
    )


def product_detail(product: Product, quantity: int = 0) -> str:
    """Build product detail message body."""
    description = product.description or "Tidak ada deskripsi untuk produk ini"
    category_label = product.category.name if product.category else "Uncategory"
    category_emoji = product.category.emoji if product.category else "📦"
    base_lines = [
        f"⌊ <b>{product.name}</b> ⌉",
        f"🗒️ {description}",
        "",
        f"💲 <b>Harga:</b> {product.formatted_price}",
        f"📦 <b>Stok Tersedia:</b> {product.stock}x",
        f"{category_emoji} <b>Category:</b> {category_label}",
    ]

    if quantity > 0:
        total_cents = product.price_cents * quantity
        total_rp = (
            f"Rp {total_cents / 100:,.2f}".replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )
        base_lines.extend(
            [
                "",
                f"🛍️ <b>In Cart:</b> {quantity}x",
                f"💰 <b>Total Dibayar:</b> {total_rp}",
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
        "⛺ <b>Keranjang Belanja Kamu</b>\n"
        "✅ Pastikan jumlah item dan harga sudah pas ya.\n"
        f"{EMOJI_SEPARATOR}\n"
        f"📦 <b>Total Item:</b> {total_items}\n"
        f"💵 <b>Total Dibayar:</b> {total_rp}\n\n"
        f"{body}\n\n"
        "🚫 <i>Kami tidak menerima komplain setelah pembayaran selesai.</i>"
    )


def payment_prompt(
    total_rp: str, user_name: str, balance_rp: str, bank_id: str | None
) -> str:
    """Prompt user to choose payment method."""
    lines = [
        "🧊 <b>Silakan Pilih Metode Pembayaran</b>",
        "",
        "💳 <b>Informasi Tagihan</b>",
        f"— Total Dibayar: <b>{total_rp}</b>",
        f"— Date Created: {datetime.now().strftime('%d/%m/%y')}",
        "",
        "🙋 <b>Informasi Kamu</b>",
        f"— Name: {user_name}",
        f"— Saldo Kamu: <b>{balance_rp}</b>",
        f"— Bank Id: {bank_id or '-'}",
        "— Status Akun: <b>Aktif</b> ✅",
    ]
    return "\n".join(lines)


def payment_loading() -> str:
    """Message shown while invoice is being prepared."""
    return "🎲 <b>Sedang memuat pembayaranmu</b>, harap tunggu sebentar ya... ⏳"


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
        f"🏷️ <b>Invoice Berhasil Dibuat</b>\n<code>{invoice_id}</code>\n\n"
        "🛍️ <b>Informasi Item:</b>\n"
        f"— Total Harga: <b>{total_rp}</b>\n"
        f"— Jumlah Item: <b>{len(items)}x</b>\n"
        f"— List Yang Dibeli:\n{items_block}\n\n"
        "💰 <b>Informasi Pembayaran:</b>\n"
        f"— ID Transaksi: <code>{invoice_id}</code>\n"
        f"— Tanggal Dibuat: {created_at}\n"
        f"— Total Dibayar: <b>{total_rp}</b>\n"
        f"— Expired In: <b>{expires_in}</b> ⏰\n"
    )


def payment_expired(invoice_id: str) -> str:
    """Notify that invoice has expired."""
    return (
        f"📜 <b>Tagihan Kadaluarsa</b>\n<code>{invoice_id}</code>\n\n"
        "⚠️ Tagihan kamu sudah tidak aktif.\n"
        "🔁 Silakan ulangi pembelian untuk mendapatkan tagihan QRIS baru.\n"
        "💬 Kalau butuh bantuan, hubungi admin ya!"
    )


def payment_success(product_lines: list[str]) -> str:
    """Message shown after successful payment."""
    return (
        "🎉 <b>Pembayaran Berhasil!</b> ✅\n"
        "✨ Terima kasih sudah belanja di toko kami.\n\n"
        "📦 <b>Detail Produk:</b>\n"
        f"{EMOJI_SEPARATOR}\n"
        f"{chr(10).join(product_lines)}\n\n"
        "📄 <i>S&K berlaku ya. Selamat menikmati layanan!</i> 😄"
    )


def generic_error() -> str:
    """Fallback error message."""
    return (
        "⚠️ <b>Aduh, sistem lagi sibuk nih.</b>\n"
        "💡 Silakan coba lagi dalam beberapa saat atau kontak admin ya.\n"
        "🙏 Terima kasih sudah sabar menunggu."
    )
