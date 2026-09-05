import hashlib
import hmac

import pytest

from app.db.models import AuditEvent, CheckoutProposal
from app.domain.errors import PaymentVerificationFailed, RazorpayOrderCreationFailed
from app.services.execution_service import ExecutionService
from app.services.payment_service import verify_checkout_payment
from tests.integration.test_execution import FakeRazorpay, allowed_proposal


class PaymentRazorpay(FakeRazorpay):
    def __init__(self, payment: dict | None = None, fail_lookup: bool = False) -> None:
        super().__init__()
        self.payment = payment or {}
        self.fail_lookup = fail_lookup

    def fetch_payment(self, payment_id: str):
        if self.fail_lookup:
            raise RazorpayOrderCreationFailed("lookup unavailable")
        return {"id": payment_id, **self.payment}


def signed(secret: str, order_id: str, payment_id: str) -> str:
    return hmac.new(secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()


def executed(db):
    _, proposal = allowed_proposal(db)
    adapter = PaymentRazorpay()
    order = ExecutionService(db, adapter).execute(proposal.id)
    adapter.payment = {"order_id": order["id"], "amount": proposal.expected_amount_paise, "currency": proposal.currency, "status": "captured"}
    return proposal, order, adapter


def test_real_checkout_signature_and_provider_facts_are_both_required(db) -> None:
    proposal, order, adapter = executed(db)
    secret = "test-secret"
    result = verify_checkout_payment(db, proposal.id, razorpay_order_id=order["id"], razorpay_payment_id="pay_verified001", razorpay_signature=signed(secret, order["id"], "pay_verified001"), key_secret=secret, razorpay=adapter)
    assert result["status"] == "VERIFIED"
    assert db.get(CheckoutProposal, proposal.id).status == "PAID"
    assert db.query(AuditEvent).filter_by(event_type="RAZORPAY_PAYMENT_VERIFIED").count() == 1


@pytest.mark.parametrize("failure", ["signature", "amount", "status", "lookup"])
def test_payment_verification_fails_closed(db, failure) -> None:
    proposal, order, adapter = executed(db)
    secret = "test-secret"
    signature = signed(secret, order["id"], "pay_verified002")
    if failure == "signature": signature = "0" * 64
    if failure == "amount": adapter.payment["amount"] += 1
    if failure == "status": adapter.payment["status"] = "failed"
    if failure == "lookup": adapter.fail_lookup = True
    with pytest.raises(PaymentVerificationFailed):
        verify_checkout_payment(db, proposal.id, razorpay_order_id=order["id"], razorpay_payment_id="pay_verified002", razorpay_signature=signature, key_secret=secret, razorpay=adapter)
    assert db.get(CheckoutProposal, proposal.id).status in {"ORDER_CREATED", "EXECUTED"}
