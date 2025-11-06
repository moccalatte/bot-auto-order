"""Product content management service for digital inventory."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional
from uuid import UUID

from src.services.postgres import get_pool

logger = logging.getLogger(__name__)


async def add_product_content(product_id: int, content: str) -> int:
    """
    Add a single product content/stock item.

    Args:
        product_id: The product ID
        content: The actual product data (credentials, code, etc)

    Returns:
        ID of the created content record
    """
    pool = await get_pool()
    async with pool.acquire() as connection:
        async with connection.transaction():
            # Insert content
            content_row = await connection.fetchrow(
                """
                INSERT INTO product_contents (product_id, content, is_used)
                VALUES ($1, $2, FALSE)
                RETURNING id;
                """,
                product_id,
                content,
            )

            # Update product stock count
            await connection.execute(
                """
                UPDATE products
                SET stock = (
                    SELECT COUNT(*) FROM product_contents
                    WHERE product_id = $1 AND is_used = FALSE
                ),
                updated_at = NOW()
                WHERE id = $1;
                """,
                product_id,
            )

            logger.info(
                "[product_content] Added content for product_id=%s, content_id=%s",
                product_id,
                content_row["id"],
            )

            return content_row["id"]


async def get_available_content(product_id: int, quantity: int = 1) -> List[Dict]:
    """
    Get available (unused) content for a product.

    Args:
        product_id: The product ID
        quantity: Number of contents to retrieve

    Returns:
        List of content records
    """
    pool = await get_pool()
    async with pool.acquire() as connection:
        rows = await connection.fetch(
            """
            SELECT id, product_id, content, created_at
            FROM product_contents
            WHERE product_id = $1 AND is_used = FALSE
            ORDER BY created_at ASC
            LIMIT $2
            FOR UPDATE SKIP LOCKED;
            """,
            product_id,
            quantity,
        )
        return [dict(row) for row in rows]


async def mark_content_as_used(content_id: int, order_id: UUID) -> bool:
    """
    Mark a product content as used by an order.

    Args:
        content_id: The content ID
        order_id: The order that is using this content

    Returns:
        True if marked successfully
    """
    pool = await get_pool()
    async with pool.acquire() as connection:
        async with connection.transaction():
            result = await connection.execute(
                """
                UPDATE product_contents
                SET is_used = TRUE,
                    used_by_order_id = $2,
                    used_at = NOW()
                WHERE id = $1 AND is_used = FALSE;
                """,
                content_id,
                order_id,
            )

            # Update product stock
            product_row = await connection.fetchrow(
                """
                SELECT product_id FROM product_contents WHERE id = $1;
                """,
                content_id,
            )

            if product_row:
                await connection.execute(
                    """
                    UPDATE products
                    SET stock = (
                        SELECT COUNT(*) FROM product_contents
                        WHERE product_id = $1 AND is_used = FALSE
                    ),
                    updated_at = NOW()
                    WHERE id = $1;
                    """,
                    product_row["product_id"],
                )

            success = result.endswith("1")
            if success:
                logger.info(
                    "[product_content] Marked content_id=%s as used by order=%s",
                    content_id,
                    order_id,
                )
            return success


async def get_content_count(product_id: int) -> int:
    """
    Get count of available (unused) contents for a product.

    Args:
        product_id: The product ID

    Returns:
        Count of available contents
    """
    pool = await get_pool()
    async with pool.acquire() as connection:
        count = await connection.fetchval(
            """
            SELECT COUNT(*) FROM product_contents
            WHERE product_id = $1 AND is_used = FALSE;
            """,
            product_id,
        )
        return count or 0


async def delete_product_content(content_id: int) -> bool:
    """
    Delete a specific product content (only if unused).

    Args:
        content_id: The content ID to delete

    Returns:
        True if deleted successfully
    """
    pool = await get_pool()
    async with pool.acquire() as connection:
        async with connection.transaction():
            # Get product_id before deletion
            product_row = await connection.fetchrow(
                """
                SELECT product_id FROM product_contents
                WHERE id = $1 AND is_used = FALSE;
                """,
                content_id,
            )

            if not product_row:
                return False

            product_id = product_row["product_id"]

            # Delete the content
            result = await connection.execute(
                """
                DELETE FROM product_contents
                WHERE id = $1 AND is_used = FALSE;
                """,
                content_id,
            )

            # Update product stock
            await connection.execute(
                """
                UPDATE products
                SET stock = (
                    SELECT COUNT(*) FROM product_contents
                    WHERE product_id = $1 AND is_used = FALSE
                ),
                updated_at = NOW()
                WHERE id = $1;
                """,
                product_id,
            )

            success = result.endswith("1")
            if success:
                logger.info(
                    "[product_content] Deleted content_id=%s for product_id=%s",
                    content_id,
                    product_id,
                )
            return success


async def list_product_contents(
    product_id: int, include_used: bool = False, limit: int = 50, offset: int = 0
) -> List[Dict]:
    """
    List all contents for a product.

    Args:
        product_id: The product ID
        include_used: Whether to include used contents
        limit: Max number of records to return
        offset: Pagination offset

    Returns:
        List of content records
    """
    pool = await get_pool()
    async with pool.acquire() as connection:
        if include_used:
            query = """
                SELECT
                    id,
                    product_id,
                    content,
                    is_used,
                    used_by_order_id,
                    created_at,
                    used_at
                FROM product_contents
                WHERE product_id = $1
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3;
            """
        else:
            query = """
                SELECT
                    id,
                    product_id,
                    content,
                    is_used,
                    created_at
                FROM product_contents
                WHERE product_id = $1 AND is_used = FALSE
                ORDER BY created_at ASC
                LIMIT $2 OFFSET $3;
            """

        rows = await connection.fetch(query, product_id, limit, offset)
        return [dict(row) for row in rows]


async def get_order_contents(order_id: UUID) -> List[Dict]:
    """
    Get all product contents that were delivered for an order.

    Args:
        order_id: The order UUID

    Returns:
        List of content records with product info
    """
    pool = await get_pool()
    async with pool.acquire() as connection:
        rows = await connection.fetch(
            """
            SELECT
                pc.id,
                pc.content,
                pc.used_at,
                p.id as product_id,
                p.name as product_name,
                p.code as product_code
            FROM product_contents pc
            JOIN products p ON pc.product_id = p.id
            WHERE pc.used_by_order_id = $1
            ORDER BY pc.used_at ASC;
            """,
            order_id,
        )
        return [dict(row) for row in rows]


async def recalculate_all_stock() -> None:
    """
    Recalculate stock for all products based on unused content count.
    This is useful for fixing stock inconsistencies.
    """
    pool = await get_pool()
    async with pool.acquire() as connection:
        await connection.execute(
            """
            UPDATE products
            SET stock = (
                SELECT COUNT(*) FROM product_contents
                WHERE product_contents.product_id = products.id
                AND is_used = FALSE
            ),
            updated_at = NOW();
            """
        )
        logger.info("[product_content] Recalculated stock for all products")
