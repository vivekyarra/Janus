from datetime import datetime, timedelta, timezone

import pytest

from app.db.models import AuditEvent, CheckoutProposal, Mandate
from app.domain.errors import AuthorizationDenied, RazorpayOrderCreationFailed
from app.repositories.catalog import seed_catalog
from app.services.execution_service import ExecutionService
from app.services.signature_service import SignatureService, canonical_json_bytes, canonical_mandate_payload, payload_sha256


class FakeRazorpay:
    def __init__(self, fail: bool = False) -> None:
        self.calls = []
        self.fail = fail

    def create_order(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise RazorpayOrderCreationFailed("simulated test failure")
        return {"id": "order_test_001", "status": "created", **kwargs}


def allowed_proposal(db, *, product_id="prod_a", status="ALLOWED", agent_request_id="req-1"):
    seed_catalog(db)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    values = {
        "id": "mnd_exec", "instruction_text": "Buy headphones under INR 20,000",
        "hard_constraints": {"max_amount_paise": 2_000_000, "allowed_currencies": ["INR"], "allowed_merchants": ["merchant_demo"], "allowed_categories": ["headphones"], "allowed_conditions": ["new"], "max_quantity": 1, "max_executions": 1},
        "semantic_constraints": [], "expires_at": now + timedelta(hours=1), "version": 1, "max_executions": 1,
    }
    signer = SignatureService()
    canonical = canonical_json_bytes(canonical_mandate_payload(values))
    mandate = Mandate(**values, signed_version=1, status="ACTIVE", execution_count=0, canonical_payload=canonical.decode(), payload_hash=payload_sha256(canonical), signature=signer.sign(canonical), public_key=signer.public_key_pem)
    db.add(mandate)
    db.flush()
    product = db.get(__import__("app.db.models", fromlist=["Product"]).Product, product_id)
    proposal = CheckoutProposal(id="prp_exec", mandate_id=mandate.id, mandate_version=1, product_id=product.id, quantity=1, agent_request_id=agent_request_id, expected_amount_paise=product.price_paise, currency=product.currency, status=status, decision={})
    db.add(proposal)
    db.commit()
    return mandate, proposal


def test_valid_proposal_invokes_razorpay_once_and_audits(db) -> None:
    mandate, proposal = allowed_proposal(db)
    adapter = FakeRazorpay()
    order = ExecutionService(db, adapter).execute(proposal.id)
    assert order["id"] == "order_test_001"
    assert len(adapter.calls) == 1
    assert db.get(CheckoutProposal, proposal.id).status in {"ORDER_CREATED", "EXECUTED"}
    assert db.get(Mandate, mandate.id).status == "CONSUMED"
    assert {event.event_type for event in db.query(AuditEvent)} >= {"EXECUTION_RESERVED", "RAZORPAY_ORDER_CREATED"}


def test_hard_invalid_proposal_never_invokes_razorpay(db) -> None:
    mandate, proposal = allowed_proposal(db, product_id="prod_b")
    adapter = FakeRazorpay()
    with pytest.raises(AuthorizationDenied):
        ExecutionService(db, adapter).execute(proposal.id)
    assert adapter.calls == []
    assert db.get(CheckoutProposal, proposal.id).status == "BLOCKED"
    event = db.query(AuditEvent).filter_by(event_type="EXECUTION_BLOCKED").one()
    assert event.payload["razorpay_called"] is False


def test_duplicate_execution_returns_same_order(db) -> None:
    _, proposal = allowed_proposal(db)
    adapter = FakeRazorpay()
    first = ExecutionService(db, adapter).execute(proposal.id)
    for _ in range(19):
        replay = ExecutionService(db, adapter).execute(proposal.id)
        assert replay["id"] == first["id"]
        assert replay["idempotent_replay"] is True
    assert len(adapter.calls) == 1


def test_razorpay_failure_fails_closed_and_is_audited(db) -> None:
    mandate, proposal = allowed_proposal(db)
    adapter = FakeRazorpay(fail=True)
    with pytest.raises(RazorpayOrderCreationFailed):
        ExecutionService(db, adapter).execute(proposal.id)
    assert len(adapter.calls) == 1
    assert db.get(CheckoutProposal, proposal.id).status == "FAILED"
    # Verify our critical fix: execution reservation rolled back so mandate slot is not burned
    assert db.get(Mandate, mandate.id).execution_count == 0
    assert db.get(Mandate, mandate.id).status == "ACTIVE"
    event = db.query(AuditEvent).filter_by(event_type="EXECUTION_BLOCKED").one()
    assert event.payload["outcome"] == "failed_closed"
    assert event.payload.get("execution_count_rolled_back") is True


def test_revoked_mandate_blocks_execution_before_adapter(db) -> None:
    mandate, proposal = allowed_proposal(db)
    mandate.status = "REVOKED"
    mandate.revoked_at = datetime.now(timezone.utc)
    mandate.version += 1
    db.commit()
    adapter = FakeRazorpay()
    with pytest.raises(AuthorizationDenied):
        ExecutionService(db, adapter).execute(proposal.id)
    assert adapter.calls == []
