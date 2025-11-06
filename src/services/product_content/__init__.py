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

    Raises:
        ValueError: If validation fails or content is duplicate
    """
    if not content or not content.strip():
        raise ValueError("Content tidak boleh kosong")

    # Validasi product exists
    pool = await get_pool()
    async with pool.acquire() as connection:
        product_exists = await connection.fetchval(
            "SELECT EXISTS(SELECT 1 FROM products WHERE id = $1)",
            product_id,
        )
        if not product_exists:
            raise ValueError(f"Produk dengan ID {product_id} tidak ditemukan")

        # Check for duplicate content
        duplicate_exists = await connection.fetchval(
            "SELECT EXISTS(SELECT 1 FROM product_contents WHERE content = $1)",
            content.strip(),
        )
        if duplicate_exists:
            raise ValueError(
                "Content ini sudah ada di database. Setiap content harus unik."
            )

        async with connection.transaction():
            try:
                # Insert content
                content_row = await connection.fetchrow(
                    """
                    INSERT INTO product_contents (product_id, content, is_used)
                    VALUES ($1, $2, FALSE)
                    RETURNING id;
                    """,
                    product_id,
                    content.strip(),
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

                content_id = content_row["id"]
                logger.info(
                    "[product_content] Added content for product_id=%s, content_id=%s",
                    product_id,
                    content_id,
                )

                return content_id

            except Exception as e:
                error_msg = str(e)
                if "duplicate key" in error_msg.lower():
                    raise ValueError(
                        "Content ini sudah ada di database. Setiap content harus unik."
                    ) from e
                raise


async def add_bulk_product_content(
    product_id: int, contents: List[str]
) -> Dict[str, any]:
    """
    Add multiple product contents in bulk.

    Args:
        product_id: The product ID
        contents: List of content strings

    Returns:
        Dict with success count, failed items, and errors

    Raises:
        ValueError: If product doesn't exist or no valid contents
    """
    if not contents:
        raise ValueError("Daftar content tidak boleh kosong")

    # Validasi product exists
    pool = await get_pool()
    async with pool.acquire() as connection:
        product_exists = await connection.fetchval(
            "SELECT EXISTS(SELECT 1 FROM products WHERE id = $1)",
            product_id,
        )
        if not product_exists:
            raise ValueError(f"Produk dengan ID {product_id} tidak ditemukan")

    results = {
        "success": 0,
        "failed": 0,
        "errors": [],
        "duplicate_contents": [],
    }

    for idx, content in enumerate(contents):
        if not content or not content.strip():
            results["failed"] += 1
            results["errors"].append(f"Baris {idx + 1}: Content kosong")
            continue

        try:
            await add_product_content(product_id, content)
            results["success"] += 1
        except ValueError as e:
            results["failed"] += 1
            error_detail = f"Baris {idx + 1}: {str(e)}"
            results["errors"].append(error_detail)
            if "sudah ada" in str(e).lower() or "duplicate" in str(e).lower():
                results["duplicate_contents"].append(content.strip())
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(
                f"Baris {idx + 1}: Error tidak diketahui - {str(e)}"
            )

    logger.info(
        "[product_content] Bulk add for product_id=%s: success=%s, failed=%s",
        product_id,
        results["success"],
        results["failed"],
    )

    return results


async def get_available_content(product_id: int, quantity: int = 1) -> List[Dict]:
    """
    Get available (unused) content for a product.

    Args:
        product_id: The product ID
        quantity: Number of contents to retrieve

    Returns:
        List of content records

    Raises:
        ValueError: If invalid parameters
    """
    if quantity <= 0:
        raise ValueError("Quantity harus lebih dari 0")

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

    Raises:
        ValueError: If content not found or already used
    """
    pool = await get_pool()
    async with pool.acquire() as connection:
        async with connection.transaction():
            # Check if content exists and not used
            content_check = await connection.fetchrow(
                """
                SELECT product_id, is_used
                FROM product_contents
                WHERE id = $1
                FOR UPDATE;
                """,
                content_id,
            )

            if not content_check:
                raise ValueError(f"Content dengan ID {content_id} tidak ditemukan")

            if content_check["is_used"]:
                raise ValueError(f"Content dengan ID {content_id} sudah digunakan")

            # Mark as used
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
            product_id = content_check["product_id"]
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

    Raises:
        ValueError: If content is already used or not found
    """
    pool = await get_pool()
    async with pool.acquire() as connection:
        async with connection.transaction():
            # Check if content exists and is not used
            content_row = await connection.fetchrow(
                """
                SELECT product_id, is_used FROM product_contents
                WHERE id = $1;
                """,
                content_id,
            )

            if not content_row:
                raise ValueError(f"Content dengan ID {content_id} tidak ditemukan")

            if content_row["is_used"]:
                raise ValueError(
                    f"Content dengan ID {content_id} sudah digunakan dan tidak dapat dihapus"
                )

            product_id = content_row["product_id"]

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

    Raises:
        ValueError: If invalid parameters
    """
    if limit <= 0:
        raise ValueError("Limit harus lebih dari 0")

    if offset < 0:
        raise ValueError("Offset tidak boleh negatif")

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


async def recalculate_all_stock() -> Dict[str, int]:
    """
    Recalculate stock for all products based on unused content count.
    This is useful for fixing stock inconsistencies.

    Returns:
        Dict with count of products updated
    """
    pool = await get_pool()
    async with pool.acquire() as connection:
        result = await connection.execute(
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

        # Extract number of rows updated
        try:
            updated_count = int(result.split(" ")[1])
        except (IndexError, ValueError):
            updated_count = 0

        logger.info(
            "[product_content] Recalculated stock for %s products", updated_count
        )

        return {"updated_count": updated_count}


async def check_content_integrity() -> Dict[str, any]:
    """
    Check for content integrity issues like:
    - Contents marked as used but no order_id
    - Contents marked as used but no used_at
    - Stock count mismatch

    Returns:
        Dict with integrity check results
    """
    pool = await get_pool()
    async with pool.acquire() as connection:
        # Check used contents without order_id
        orphaned_used = await connection.fetch(
            """
            SELECT id, product_id
            FROM product_contents
            WHERE is_used = TRUE AND used_by_order_id IS NULL;
            """
        )

        # Check used contents without used_at
        missing_used_at = await connection.fetch(
            """
            SELECT id, product_id
            FROM product_contents
            WHERE is_used = TRUE AND used_at IS NULL;
            """
        )

        # Check stock mismatches
        stock_mismatches = await connection.fetch(
            """
            SELECT
                p.id,
                p.code,
                p.name,
                p.stock as recorded_stock,
                COUNT(pc.id) FILTER (WHERE pc.is_used = FALSE) as actual_stock
            FROM products p
            LEFT JOIN product_contents pc ON pc.product_id = p.id
            GROUP BY p.id, p.code, p.name, p.stock
            HAVING p.stock != COUNT(pc.id) FILTER (WHERE pc.is_used = FALSE);
            """
        )

        results = {
            "orphaned_used_contents": [dict(r) for r in orphaned_used],
            "missing_used_at": [dict(r) for r in missing_used_at],
            "stock_mismatches": [dict(r) for r in stock_mismatches],
            "has_issues": (
                len(orphaned_used) > 0
                or len(missing_used_at) > 0
                or len(stock_mismatches) > 0
            ),
        }

        if results["has_issues"]:
            logger.warning(
                "[product_content] Integrity issues found: %s orphaned, %s missing used_at, %s stock mismatches",
                len(orphaned_used),
                len(missing_used_at),
                len(stock_mismatches),
            )
        else:
            logger.info("[product_content] Integrity check passed: no issues found")

        return results
