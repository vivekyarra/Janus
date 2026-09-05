from typing import Any, Protocol

import httpx

from app.config import Settings
from app.domain.errors import RazorpayOrderCreationFailed


class RazorpayPort(Protocol):
    def create_order(self, *, amount: int, currency: str, receipt: str, notes: dict[str, str]) -> dict[str, Any]: ...
    def fetch_payment(self, payment_id: str) -> dict[str, Any]: ...


class RazorpayAdapter:
    """The only production code allowed to call the Razorpay Orders API."""

    endpoint = "https://api.razorpay.com/v1/orders"

    def __init__(self, settings: Settings) -> None:
        self.key_id = settings.razorpay_key_id
        self.key_secret = settings.razorpay_key_secret
        if settings.razorpay_mode != "test":
            raise ValueError("JANUS v1 permits Razorpay test mode only")

    @property
    def public_key_id(self) -> str:
        return self.key_id

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
        except Exception as exc:
            # Categorize errors for timeout reconciliation
            error_str = str(exc).lower()
            exc_type = type(exc).__name__
            
            if "timeout" in error_str or exc_type == "TimeoutException":
                # Specific timeout error for reconciliation
                raise RazorpayOrderCreationFailed("RAZORPAY_TIMEOUT") from exc
            elif "network" in error_str or "connection" in error_str or exc_type in ["ConnectError", "NetworkError"]:
                # Network-related errors (DNS, connection refused, etc.)
                raise RazorpayOrderCreationFailed("NETWORK_ERROR") from exc
            elif hasattr(exc, "response") and hasattr(exc.response, "status_code"):
                # HTTP errors from Razorpay (4xx, 5xx)
                raise RazorpayOrderCreationFailed(f"RAZORPAY_HTTP_ERROR_{exc.response.status_code}") from exc
            else:
                # Other HTTP errors
                raise RazorpayOrderCreationFailed("RAZORPAY_UNKNOWN_ERROR") from exc

    def fetch_payment(self, payment_id: str) -> dict[str, Any]:
        if not self.key_id.startswith("rzp_test_") or not self.key_secret:
            raise RazorpayOrderCreationFailed("Razorpay test credentials are not configured")
        try:
            response = httpx.get(f"https://api.razorpay.com/v1/payments/{payment_id}", auth=(self.key_id, self.key_secret), timeout=15)
            response.raise_for_status()
            payment = response.json()
            if payment.get("id") != payment_id:
                raise ValueError("Razorpay returned a different payment")
            return payment
        except (httpx.HTTPError, ValueError) as exc:
            raise RazorpayOrderCreationFailed("Razorpay payment lookup failed closed") from exc
