"""Catalog service for categories and products."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Sequence

from src.services.postgres import get_pool
from src.services.product_content import delete_all_contents_for_product

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Category:
    id: int
    name: str
    slug: str
    emoji: str


@dataclass(slots=True)
class Product:
    id: int
    code: str
    name: str
    description: str | None
    price_cents: int
    stock: int
    sold_count: int
    category: Category | None = None

    @property
    def formatted_price(self) -> str:
        rupiah = self.price_cents / 100
        return f"Rp {rupiah:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


async def category_exists(category_id: int) -> bool:
    """Check if category exists and is active."""
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT id FROM categories
        WHERE id = $1 AND is_active = TRUE
        LIMIT 1;
        """,
        category_id,
    )
    return row is not None


async def list_categories() -> List[Category]:
    """Return active product categories ordered by name."""
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT id, name, slug, COALESCE(emoji, '🗂️') AS emoji
        FROM categories
        WHERE is_active = TRUE
        ORDER BY name;
        """
    )
    return [Category(**dict(row)) for row in rows]


async def list_products(limit: int = 50) -> List[Product]:
    """Return active products with optional limit."""
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT
            p.id,
            p.code,
            p.name,
            p.description,
            p.price_cents,
            p.stock,
            p.sold_count,
            c.id AS category_id,
            c.name AS category_name,
            c.slug AS category_slug,
            COALESCE(c.emoji, '🗂️') AS category_emoji
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.is_active = TRUE
        ORDER BY p.id ASC
        LIMIT $1;
        """,
        limit,
    )
    products: List[Product] = []
    for row in rows:
        data = dict(row)
        category = None
        if data.get("category_id"):
            category = Category(
                id=data["category_id"],
                name=data["category_name"],
                slug=data["category_slug"],
                emoji=data["category_emoji"],
            )
        products.append(
            Product(
                id=data["id"],
                code=data["code"],
                name=data["name"],
                description=data["description"],
                price_cents=data["price_cents"],
                stock=data["stock"],
                sold_count=data["sold_count"],
                category=category,
            )
        )
    return products


async def add_product(
    category_id: int | None,
    code: str,
    name: str,
    description: str,
    price_cents: int,
    stock: int,
) -> int:
    """
    Tambah produk baru ke database dengan validasi.

    Args:
        category_id: ID kategori (opsional, bisa NULL)
        code: Kode unik produk
        name: Nama produk
        description: Deskripsi produk
        price_cents: Harga dalam cents
        stock: Jumlah stok awal

    Returns:
        ID produk yang baru dibuat

    Raises:
        ValueError: Jika validasi gagal
    """
    # Validasi input
    if not code or not code.strip():
        raise ValueError("Kode produk tidak boleh kosong")

    if not name or not name.strip():
        raise ValueError("Nama produk tidak boleh kosong")

    if price_cents < 0:
        raise ValueError("Harga tidak boleh negatif")

    if stock < 0:
        raise ValueError("Stok tidak boleh negatif")

    # Validasi category_id jika diberikan
    if category_id is not None:
        if not await category_exists(category_id):
            raise ValueError(
                f"Kategori dengan ID {category_id} tidak ditemukan atau tidak aktif"
            )

    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO products (category_id, code, name, description, price_cents, stock)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id;
                """,
                category_id,
                code.strip(),
                name.strip(),
                description.strip() if description else None,
                price_cents,
                stock,
            )
            product_id = row["id"]
            logger.info(
                "[catalog] Added product id=%s code=%s name=%s", product_id, code, name
            )
            return product_id
        except Exception as e:
            error_msg = str(e)
            if "duplicate key" in error_msg.lower() and "code" in error_msg.lower():
                raise ValueError(f"Produk dengan kode '{code}' sudah ada") from e
            raise


async def edit_product(product_id: int, **fields) -> None:
    """
    Edit produk di database dengan validasi.

    Args:
        product_id: ID produk yang akan diedit
        **fields: Field yang akan diupdate

    Raises:
        ValueError: Jika validasi gagal
    """
    if not fields:
        raise ValueError("Tidak ada field yang akan diupdate")

    # Validasi category_id jika ada di fields
    if "category_id" in fields and fields["category_id"] is not None:
        if not await category_exists(fields["category_id"]):
            raise ValueError(
                f"Kategori dengan ID {fields['category_id']} tidak ditemukan atau tidak aktif"
            )

    # Validasi data input
    if "price_cents" in fields and fields["price_cents"] < 0:
        raise ValueError("Harga tidak boleh negatif")

    if "stock" in fields and fields["stock"] < 0:
        raise ValueError("Stok tidak boleh negatif")

    if "code" in fields and (not fields["code"] or not fields["code"].strip()):
        raise ValueError("Kode produk tidak boleh kosong")

    if "name" in fields and (not fields["name"] or not fields["name"].strip()):
        raise ValueError("Nama produk tidak boleh kosong")

    # Strip string fields
    if "code" in fields and isinstance(fields["code"], str):
        fields["code"] = fields["code"].strip()
    if "name" in fields and isinstance(fields["name"], str):
        fields["name"] = fields["name"].strip()
    if "description" in fields and isinstance(fields["description"], str):
        fields["description"] = fields["description"].strip() or None

    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            sets = ", ".join([f"{k} = ${i + 2}" for i, k in enumerate(fields.keys())])
            values = [product_id] + list(fields.values())
            result = await conn.execute(
                f"UPDATE products SET {sets}, updated_at = NOW() WHERE id = $1;",
                *values,
            )

            if result == "UPDATE 0":
                raise ValueError(f"Produk dengan ID {product_id} tidak ditemukan")

            logger.info(
                "[catalog] Updated product id=%s fields=%s",
                product_id,
                list(fields.keys()),
            )
        except ValueError:
            raise
        except Exception as e:
            error_msg = str(e)
            if "duplicate key" in error_msg.lower() and "code" in error_msg.lower():
                raise ValueError(
                    f"Produk dengan kode '{fields.get('code')}' sudah ada"
                ) from e
            raise


async def delete_product(product_id: int, *, force: bool = False) -> None:
    """
    Hapus produk dari database beserta semua isinya (product_contents).

    CATATAN: Produk tidak dapat dihapus jika sudah ada order yang menggunakan produk ini,
    kecuali jika force=True. Dengan force=True, produk akan disembunyikan saja (stok=0)
    untuk menjaga integritas data historis order.

    Args:
        product_id: ID produk yang akan dihapus
        force: Jika True dan ada order, akan soft-delete (set stok=0) instead of hard delete

    Raises:
        ValueError: Jika produk tidak dapat dihapus
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Cek apakah ada order_items yang reference produk ini
            order_check = await conn.fetchval(
                "SELECT COUNT(*) FROM order_items WHERE product_id = $1;",
                product_id,
            )

            if order_check > 0:
                if not force:
                    raise ValueError(
                        f"⚠️ Produk ini sudah digunakan di {order_check} order.\n\n"
                        "Produk tidak dapat dihapus untuk menjaga data historis order. "
                        "Namun produk akan disembunyikan dengan mengosongkan semua stok."
                    )

                # Soft delete: Hapus semua product_contents sehingga stok=0
                # Produk tetap ada di database untuk referensi order_items
                await delete_all_contents_for_product(product_id)

                logger.info(
                    "[catalog] Soft-deleted product id=%s (removed all contents, keeping product for order history)",
                    product_id,
                )
                return

            # Hard delete: Tidak ada order yang reference, aman untuk hapus
            # Hapus semua product_contents terkait
            await delete_all_contents_for_product(product_id)

            # Hapus produk
            result = await conn.execute(
                "DELETE FROM products WHERE id = $1;", product_id
            )

            if result == "DELETE 0":
                raise ValueError(f"Produk dengan ID {product_id} tidak ditemukan")

            logger.info(
                "[catalog] Hard-deleted product id=%s and its contents", product_id
            )


async def list_products_by_category(category_slug: str) -> Sequence[Product]:
    """Return products filtered by category slug."""
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT
            p.id,
            p.code,
            p.name,
            p.description,
            p.price_cents,
            p.stock,
            p.sold_count,
            c.id AS category_id,
            c.name AS category_name,
            c.slug AS category_slug,
            COALESCE(c.emoji, '🗂️') AS category_emoji
        FROM products p
        INNER JOIN categories c ON p.category_id = c.id
        WHERE c.slug = $1
          AND p.is_active = TRUE
        ORDER BY p.id ASC;
        """,
        category_slug,
    )
    products = []
    for row in rows:
        data = dict(row)
        category = Category(
            id=data["category_id"],
            name=data["category_name"],
            slug=data["category_slug"],
            emoji=data["category_emoji"],
        )
        products.append(
            Product(
                id=data["id"],
                code=data["code"],
                name=data["name"],
                description=data["description"],
                price_cents=data["price_cents"],
                stock=data["stock"],
                sold_count=data["sold_count"],
                category=category,
            )
        )
    return products


async def get_product(product_id: int) -> Product | None:
    """Fetch single product by ID."""
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT
            p.id,
            p.code,
            p.name,
            p.description,
            p.price_cents,
            p.stock,
            p.sold_count,
            c.id AS category_id,
            c.name AS category_name,
            c.slug AS category_slug,
            COALESCE(c.emoji, '🗂️') AS category_emoji
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.id = $1;
        """,
        product_id,
    )
    if row is None:
        return None
    data = dict(row)
    category = None
    if data.get("category_id"):
        category = Category(
            id=data["category_id"],
            name=data["category_name"],
            slug=data["category_slug"],
            emoji=data["category_emoji"],
        )
    return Product(
        id=data["id"],
        code=data["code"],
        name=data["name"],
        description=data["description"],
        price_cents=data["price_cents"],
        stock=data["stock"],
        sold_count=data["sold_count"],
        category=category,
    )


async def product_exists(product_id: int) -> bool:
    """Check if product exists."""
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT id FROM products
        WHERE id = $1
        LIMIT 1;
        """,
        product_id,
    )
    return row is not None


async def product_is_active(product_id: int) -> bool:
    """Check if product exists and is active."""
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT id FROM products
        WHERE id = $1 AND is_active = TRUE
        LIMIT 1;
        """,
        product_id,
    )
    return row is not None
