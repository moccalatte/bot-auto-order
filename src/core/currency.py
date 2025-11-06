"""Currency helpers for Rupiah formatting and fee calculations."""

from __future__ import annotations

import math


def format_rupiah(amount_cents: int) -> str:
    """Convert integer cents to formatted Rupiah string."""
    rupiah = amount_cents / 100
    return f"Rp {rupiah:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def calculate_gateway_fee(amount_cents: int) -> int:
    """Calculate Pakasir QRIS fee (0.7% + Rp310)."""
    if amount_cents <= 0:
        return 0
    percent_fee = math.ceil(amount_cents * 7 / 1000)
    fixed_fee_cents = 310 * 100
    return percent_fee + fixed_fee_cents
