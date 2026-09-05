from typing import Any, Protocol

import httpx

from app.config import Settings
from app.domain.errors import RazorpayOrderCreationFailed


class RazorpayPort(Protocol):
    def create_order(self, *, amount: int, currency: str, receipt: str, notes: dict[str, str]) -> dict[str, Any]: ...


class RazorpayAdapter:
    """The only production code allowed to call the Razorpay Orders API."""

    endpoint = "https://api.razorpay.com/v1/orders"

    def __init__(self, settings: Settings) -> None:
        self.key_id = settings.razorpay_key_id
        self.key_secret = settings.razorpay_key_secret
        if settings.razorpay_mode != "test":
            raise ValueError("JANUS v1 permits Razorpay test mode only")

    def create_order(self, *, amount: int, currency: str, receipt: str, notes: dict[str, str]) -> dict[str, Any]:
        if not self.key_id.startswith("rzp_test_") or not self.key_secret:
            raise RazorpayOrderCreationFailed("Razorpay test credentials are not configured")
        try:
            response = httpx.post(
                self.endpoint,
                auth=(self.key_id, self.key_secret),
                json={"amount": amount, "currency": currency, "receipt": receipt[:40], "notes": notes},
                timeout=15,
            )
            response.raise_for_status()
            order = response.json()
            if not isinstance(order.get("id"), str) or not order["id"].startswith("order_"):
                raise ValueError("Razorpay response did not contain an order id")
            return order
        except (httpx.HTTPError, ValueError) as exc:
            raise RazorpayOrderCreationFailed("Razorpay order creation failed closed") from exc

