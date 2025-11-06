import importlib
import math
import unittest

from src.core.currency import calculate_gateway_fee, format_rupiah

try:
    messages = importlib.import_module("src.bot.messages")
    MESSAGES_AVAILABLE = True
except ModuleNotFoundError:
    messages = None
    MESSAGES_AVAILABLE = False

try:
    keyboards = importlib.import_module("src.bot.keyboards")
    TELEGRAM_AVAILABLE = True
except ModuleNotFoundError:
    keyboards = None
    TELEGRAM_AVAILABLE = False


class PaymentsFormattingTest(unittest.TestCase):
    """Unit tests for payment formatting helpers."""

    def test_calculate_gateway_fee_standard_amount(self) -> None:
        amount_cents = 30_000 * 100
        fee_cents = calculate_gateway_fee(amount_cents)
        self.assertEqual(fee_cents, 52_000)

    def test_calculate_gateway_fee_rounding_up(self) -> None:
        amount_cents = 123_450  # Rp 1.234,50
        fee_cents = calculate_gateway_fee(amount_cents)
        percent_component = math.ceil(amount_cents * 7 / 1000)
        self.assertEqual(fee_cents, percent_component + 31_000)

    @unittest.skipUnless(TELEGRAM_AVAILABLE, "python-telegram-bot not installed")
    def test_cart_inline_keyboard_items_present(self) -> None:
        keyboard = keyboards.cart_inline_keyboard(has_items=True)  # type: ignore[union-attr]
        callbacks = [
            button.callback_data
            for row in keyboard.inline_keyboard
            for button in row
            if button.callback_data
        ]
        self.assertIn("cart:pay", callbacks)

    @unittest.skipUnless(TELEGRAM_AVAILABLE, "python-telegram-bot not installed")
    def test_cart_inline_keyboard_empty_cart(self) -> None:
        keyboard = keyboards.cart_inline_keyboard(has_items=False)  # type: ignore[union-attr]
        callbacks = [
            button.callback_data
            for row in keyboard.inline_keyboard
            for button in row
            if button.callback_data
        ]
        self.assertNotIn("cart:pay", callbacks)
        self.assertIn("category:all", callbacks)

    @unittest.skipUnless(MESSAGES_AVAILABLE, "bot message templates unavailable")
    def test_deposit_invoice_detail_contains_totals(self) -> None:
        text = messages.deposit_invoice_detail(  # type: ignore[union-attr]
            invoice_id="dp123",
            amount_rp=format_rupiah(200_000),
            fee_rp=format_rupiah(40_000),
            payable_rp=format_rupiah(240_000),
            expires_in="5 Menit",
            created_at="2025-11-06T11:26:00+07:00",
        )
        self.assertIn("dp123", text)
        self.assertIn("Biaya Layanan Pakasir", text)
        self.assertIn("Total Dibayar", text)


if __name__ == "__main__":
    unittest.main()
