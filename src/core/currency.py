"""Currency helpers for Rupiah formatting and fee calculations."""

from __future__ import annotations


def format_rupiah(amount_cents: int) -> str:
    """Convert integer cents to formatted Rupiah string."""
    rupiah = amount_cents / 100
    return f"Rp {rupiah:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def calculate_gateway_fee(amount_cents: int) -> int:
    """
    Calculate Pakasir QRIS fee (0.7% + Rp310).

    NOTE: This is for DISPLAY purposes only!
    DO NOT add this fee to the amount sent to Pakasir API.
    Pakasir will automatically add the fee on their side.

    This function is kept for showing fee breakdown to users.
    """
    if amount_cents <= 0:
        return 0

    # Fee formula: 0.7% + Rp 310
    import math

    percent_fee = math.ceil(amount_cents * 7 / 1000)
    fixed_fee_cents = 310 * 100
    return percent_fee + fixed_fee_cents
