"""Currency helpers for Rupiah formatting."""

def format_rupiah(amount_cents: int) -> str:
    """Convert integer cents to formatted Rupiah string."""
    rupiah = amount_cents / 100
    return f"Rp {rupiah:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
