import pytest

from app.db.models import AuditEvent, StepUpRequest
from app.domain.errors import AuthorizationDenied
from app.services.stepup_service import approve_step_up, create_step_up, reject_step_up
from tests.integration.test_execution import FakeRazorpay, allowed_proposal


def test_step_up_approve_once_executes_exact_proposal(db) -> None:
    _, proposal = allowed_proposal(db, status="STEP_UP")
    step_up = create_step_up(db, proposal, "SEMANTIC_CONTRADICTED", {"color": "metallic gold"})
    db.commit()
    adapter = FakeRazorpay()
    order = approve_step_up(db, step_up.id, adapter)
    assert order["id"] == "order_test_001"
    assert len(adapter.calls) == 1
    assert db.get(StepUpRequest, step_up.id).status == "CONSUMED"
    with pytest.raises(AuthorizationDenied):
        approve_step_up(db, step_up.id, adapter)
    assert len(adapter.calls) == 1


def test_step_up_reject_moves_no_money(db) -> None:
    _, proposal = allowed_proposal(db, status="STEP_UP")
    step_up = create_step_up(db, proposal, "SEMANTIC_CONTRADICTED", {})
    db.commit()
    rejected = reject_step_up(db, step_up.id)
    assert rejected.status == "REJECTED"
    assert proposal.status == "BLOCKED"
    assert db.query(AuditEvent).filter_by(event_type="STEP_UP_REJECTED").count() == 1


def test_step_up_binding_tamper_is_blocked(db) -> None:
    _, proposal = allowed_proposal(db, status="STEP_UP")
    step_up = create_step_up(db, proposal, "SEMANTIC_CONTRADICTED", {})
    db.commit()
    proposal.expected_amount_paise += 1
    db.commit()
    adapter = FakeRazorpay()
    with pytest.raises(AuthorizationDenied):
        approve_step_up(db, step_up.id, adapter)
    assert adapter.calls == []

