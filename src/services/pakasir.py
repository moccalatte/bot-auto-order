"""Client for Pakasir payment gateway."""

from __future__ import annotations

import logging
from typing import Any, Dict

import httpx

from src.core.config import get_settings


logger = logging.getLogger(__name__)


class PakasirClient:
    """Wrapper for Pakasir REST API."""

    def __init__(self, *, timeout: int = 15) -> None:
        self.settings = get_settings()
        self._client = httpx.AsyncClient(timeout=timeout)

    async def create_transaction(self, method: str, order_id: str, amount_cents: int) -> Dict[str, Any]:
        payload = {
            "project": self.settings.pakasir_project_slug,
            "order_id": order_id,
            "amount": amount_cents,
            "api_key": self.settings.pakasir_api_key,
        }
        url = f"https://app.pakasir.com/api/transactioncreate/{method}"
        logger.info("🧾 Requesting Pakasir transaction for %s (%s)", order_id, method)
        response = await self._client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        logger.debug("✅ Pakasir response: %s", data)
        return data

    async def get_transaction_detail(self, order_id: str, amount_cents: int) -> Dict[str, Any]:
        params = {
            "project": self.settings.pakasir_project_slug,
            "amount": amount_cents,
            "order_id": order_id,
            "api_key": self.settings.pakasir_api_key,
        }
        url = "https://app.pakasir.com/api/transactiondetail"
        logger.info("🔍 Checking Pakasir transaction detail: %s", order_id)
        response = await self._client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    async def simulate_payment(self, order_id: str, amount_cents: int) -> Dict[str, Any]:
        payload = {
            "project": self.settings.pakasir_project_slug,
            "order_id": order_id,
            "amount": amount_cents,
            "api_key": self.settings.pakasir_api_key,
        }
        url = "https://app.pakasir.com/api/paymentsimulation"
        logger.info("🧪 Simulating Pakasir payment for %s", order_id)
        response = await self._client.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    def build_payment_url(self, order_id: str, amount_cents: int, qris_only: bool = True) -> str:
        amount = amount_cents
        url = f"{self.settings.pakasir_public_domain}/pay/{self.settings.pakasir_project_slug}/{amount}?order_id={order_id}"
        if qris_only:
            url = f"{url}&qris_only=1"
        return url

    async def aclose(self) -> None:
        await self._client.aclose()
