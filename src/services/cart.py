"""In-memory cart manager (persist to DB planned for future iteration)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Dict, List

from src.services.catalog import Product


@dataclass(slots=True)
class CartItem:
    product: Product
    quantity: int = 0

    @property
    def total_cents(self) -> int:
        return self.product.price_cents * self.quantity


@dataclass(slots=True)
class Cart:
    items: Dict[int, CartItem] = field(default_factory=dict)

    def add(self, product: Product, amount: int = 1) -> None:
        """Add a product to the cart respecting available stock."""
        item = self.items.get(product.id)
        if item is None:
            item = CartItem(product=product, quantity=0)
            self.items[product.id] = item
        item.quantity = min(product.stock, item.quantity + amount)

    def remove(self, product_id: int, amount: int = 1) -> None:
        """Remove `amount` of the product from the cart."""
        if product_id not in self.items:
            return
        item = self.items[product_id]
        item.quantity = max(0, item.quantity - amount)
        if item.quantity == 0:
            del self.items[product_id]

    def clear(self) -> None:
        """Remove every item from the cart."""
        self.items.clear()

    def total_cents(self) -> int:
        """Return total cost in cents."""
        return sum(item.total_cents for item in self.items.values())

    def total_items(self) -> int:
        """Return total item count."""
        return sum(item.quantity for item in self.items.values())

    def to_lines(self) -> List[str]:
        """Render cart items into list of human-readable lines."""
        lines = []
        for index, item in enumerate(self.items.values(), start=1):
            total_rp = item.total_cents / 100
            formatted = f"Rp {total_rp:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            lines.append(f"{index}. {item.product.name} x{item.quantity} = {formatted}")
        return lines


class CartManager:
    """Manage carts in memory per Telegram user."""

    def __init__(self) -> None:
        self._carts: Dict[int, Cart] = {}
        self._lock = asyncio.Lock()

    async def get_cart(self, user_id: int) -> Cart:
        """Fetch cart for user, creating a new one if needed."""
        async with self._lock:
            return self._carts.setdefault(user_id, Cart())

    async def clear_cart(self, user_id: int) -> None:
        """Remove stored cart for the user."""
        async with self._lock:
            self._carts.pop(user_id, None)
