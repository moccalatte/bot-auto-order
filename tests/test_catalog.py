import unittest
import asyncio
from unittest.mock import MagicMock, patch

from src.services.catalog import add_product, delete_product, get_product
from src.services.product_content import add_content, get_content_count


class TestCatalog(unittest.TestCase):
    @patch("src.services.product_content.get_pool")
    @patch("src.services.catalog.get_pool")
    def test_delete_product(self, mock_get_pool_catalog, mock_get_pool_content):
        async def run_test():
            # Mock the database connection
            mock_pool = MagicMock()
            mock_conn = MagicMock()

            async def async_magic(*args, **kwargs):
                return mock_conn

            mock_pool.acquire.return_value.__aenter__ = async_magic

            async def get_pool():
                return mock_pool

            mock_get_pool_catalog.return_value = await get_pool()
            mock_get_pool_content.return_value = await get_pool()

            async def pool_fetchrow(*args, **kwargs):
                return await mock_conn.fetchrow(*args, **kwargs)
            mock_pool.fetchrow = pool_fetchrow

            # 1. Create a product
            async def fetchrow(*args, **kwargs):
                return {"id": 1}

            mock_conn.fetchrow = fetchrow
            product_id = await add_product(
                category_id=None,
                code="TESTPROD",
                name="Test Product",
                description="A product for testing",
                price_cents=10000,
                stock=0,
            )

            # 2. Add some content to the product
            async def fetchval_add_content(*args, **kwargs):
                if "products" in args[0]:
                    return True  # for product_exists
                else:
                    return False # for duplicate_exists

            async def execute_update_stock(*args, **kwargs):
                return "UPDATE 1"

            mock_conn.fetchval = fetchval_add_content
            mock_conn.fetchrow = fetchrow
            mock_conn.execute = execute_update_stock
            await add_content(product_id, "content1")
            await add_content(product_id, "content2")

            # 3. Verify that the product and its contents exist
            async def fetchrow_product(*args, **kwargs):
                return {
                    "id": 1,
                    "code": "TESTPROD",
                    "name": "Test Product",
                    "description": "A product for testing",
                    "price_cents": 10000,
                    "stock": 2,
                    "sold_count": 0,
                    "category_id": None,
                }

            mock_conn.fetchrow = fetchrow_product
            product = await get_product(product_id)
            self.assertIsNotNone(product)

            async def fetchval_count(*args, **kwargs):
                return 2

            mock_conn.fetchval = fetchval_count
            content_count = await get_content_count(product_id)
            self.assertEqual(content_count, 2)

            # 4. Delete the product
            async def execute_delete(*args, **kwargs):
                if "UPDATE order_items" in args[0]:
                    return "UPDATE 1"
                elif "DELETE FROM products" in args[0]:
                    return "DELETE 1"
                return "DELETE 0"

            mock_conn.execute = execute_delete
            await delete_product(product_id)

            # 5. Verify that the product and its contents are deleted
            async def fetchrow_none(*args, **kwargs):
                return None

            mock_conn.fetchrow = fetchrow_none
            product = await get_product(product_id)
            self.assertIsNone(product)

            async def fetchval_zero(*args, **kwargs):
                return 0

            mock_conn.fetchval = fetchval_zero
            content_count = await get_content_count(product_id)
            self.assertEqual(content_count, 0)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
