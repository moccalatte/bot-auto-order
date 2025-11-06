import unittest
import asyncio
from unittest.mock import MagicMock, patch

from src.services.users import get_user_by_telegram_id, upsert_user


class TestUsers(unittest.TestCase):
    @patch("src.services.users.get_pool")
    def test_get_user_by_telegram_id(self, mock_get_pool):
        async def run_test():
            # Mock the database connection
            mock_pool = MagicMock()
            mock_conn = MagicMock()

            async def async_magic(*args, **kwargs):
                return mock_conn

            mock_pool.acquire.return_value.__aenter__ = async_magic

            async def get_pool():
                return mock_pool

            mock_get_pool.return_value = await get_pool()

            # 1. Upsert a user
            async def fetchrow_upsert(*args, **kwargs):
                return {"id": 1}

            mock_conn.fetchrow = fetchrow_upsert
            await upsert_user(
                telegram_id=12345,
                username="testuser",
                first_name="Test",
                last_name="User",
            )

            # 2. Get the user by telegram_id
            async def fetchrow_get(*args, **kwargs):
                return {
                    "id": 1,
                    "telegram_id": 12345,
                    "username": "testuser",
                    "first_name": "Test",
                    "last_name": "User",
                }

            mock_conn.fetchrow = fetchrow_get
            user = await get_user_by_telegram_id(12345)

            # 3. Verify the user data
            self.assertIsNotNone(user)
            self.assertEqual(user["telegram_id"], 12345)
            self.assertEqual(user["username"], "testuser")

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
