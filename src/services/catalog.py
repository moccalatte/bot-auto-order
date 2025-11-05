"""Catalog service for categories and products."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

from src.services.postgres import get_pool


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
    """Tambah produk baru ke database. category_id bisa NULL."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Make category_id nullable in schema if not already
        await conn.execute(
            "ALTER TABLE products ALTER COLUMN category_id DROP NOT NULL;"
        )
        row = await conn.fetchrow(
            """
            INSERT INTO products (category_id, code, name, description, price_cents, stock)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id;
            """,
            category_id,
            code,
            name,
            description,
            price_cents,
            stock,
        )
    return row["id"]


async def edit_product(product_id: int, **fields) -> None:
    """Edit produk di database."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        sets = ", ".join([f"{k} = ${i + 2}" for i, k in enumerate(fields.keys())])
        values = [product_id] + list(fields.values())
        await conn.execute(
            f"UPDATE products SET {sets}, updated_at = NOW() WHERE id = $1;", *values
        )


async def delete_product(product_id: int) -> None:
    """Hapus produk dari database."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM products WHERE id = $1;", product_id)


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
