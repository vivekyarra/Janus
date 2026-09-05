import hashlib
import hmac
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CheckoutProposal
from app.domain.errors import PaymentVerificationFailed
from app.domain.errors import RazorpayOrderCreationFailed
from app.integrations.razorpay_adapter import RazorpayPort
from app.services.audit_service import write_audit


def verify_checkout_payment(
    db: Session,
    proposal_id: str,
    *,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
    key_secret: str,
    razorpay: RazorpayPort,
) -> dict:
    proposal = db.scalar(select(CheckoutProposal).where(CheckoutProposal.id == proposal_id).with_for_update())
    if proposal is None or proposal.razorpay_order_id is None:
        raise PaymentVerificationFailed("Authorized order was not found")
    if proposal.status == "PAID":
        if proposal.razorpay_payment_id != razorpay_payment_id:
            raise PaymentVerificationFailed("Payment replay does not match the recorded payment")
        return {"proposal_id": proposal.id, "razorpay_order_id": proposal.razorpay_order_id, "razorpay_payment_id": proposal.razorpay_payment_id, "status": "VERIFIED", "idempotent_replay": True}
    if proposal.status != "EXECUTED" or proposal.razorpay_order_id != razorpay_order_id:
        raise PaymentVerificationFailed("Payment is not bound to this authorized order")
    if not key_secret:
        raise PaymentVerificationFailed("Payment verification key is unavailable")

    message = f"{proposal.razorpay_order_id}|{razorpay_payment_id}".encode()
    expected = hmac.new(key_secret.encode(), message, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, razorpay_signature):
        write_audit(db, "RAZORPAY_PAYMENT_VERIFICATION_FAILED", "proposal", proposal.id, {"razorpay_order_id": proposal.razorpay_order_id, "razorpay_payment_id": razorpay_payment_id, "reason_code": "SIGNATURE_MISMATCH"})
        db.commit()
        raise PaymentVerificationFailed("Razorpay payment signature did not verify")

    try:
        provider_payment = razorpay.fetch_payment(razorpay_payment_id)
    except RazorpayOrderCreationFailed as exc:
        write_audit(db, "RAZORPAY_PAYMENT_VERIFICATION_FAILED", "proposal", proposal.id, {"razorpay_order_id": proposal.razorpay_order_id, "razorpay_payment_id": razorpay_payment_id, "reason_code": "PROVIDER_LOOKUP_FAILED"})
        db.commit()
        raise PaymentVerificationFailed("Razorpay payment state could not be verified") from exc
    provider_matches = (
        provider_payment.get("order_id") == proposal.razorpay_order_id
        and provider_payment.get("amount") == proposal.expected_amount_paise
        and provider_payment.get("currency") == proposal.currency
        and provider_payment.get("status") in {"authorized", "captured"}
    )
    if not provider_matches:
        write_audit(db, "RAZORPAY_PAYMENT_VERIFICATION_FAILED", "proposal", proposal.id, {"razorpay_order_id": proposal.razorpay_order_id, "razorpay_payment_id": razorpay_payment_id, "reason_code": "PROVIDER_STATE_MISMATCH", "provider_status": provider_payment.get("status")})
        db.commit()
        raise PaymentVerificationFailed("Razorpay payment facts do not match the authorized order")

    proposal.razorpay_payment_id = razorpay_payment_id
    proposal.payment_status = "VERIFIED"
    proposal.status = "PAID"
    proposal.paid_at = datetime.now(timezone.utc)
    write_audit(db, "RAZORPAY_PAYMENT_VERIFIED", "proposal", proposal.id, {"razorpay_order_id": proposal.razorpay_order_id, "razorpay_payment_id": razorpay_payment_id, "amount": proposal.expected_amount_paise, "currency": proposal.currency, "provider_status": provider_payment["status"]})
    db.commit()
    return {"proposal_id": proposal.id, "razorpay_order_id": proposal.razorpay_order_id, "razorpay_payment_id": razorpay_payment_id, "status": "VERIFIED", "idempotent_replay": False}
