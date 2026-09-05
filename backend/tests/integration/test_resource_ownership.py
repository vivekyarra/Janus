from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.api.audit import list_audit
from app.api.mandates import get_mandate, revoke_mandate
from app.api.stepups import approve, get_step_up, reject
from app.db.models import AuditEvent, Mandate
from app.services.auth_service import Actor
from app.services.stepup_service import create_step_up
from app.services.signature_service import (
    SignatureService,
    canonical_json_bytes,
    canonical_mandate_payload,
    payload_sha256,
)
from tests.integration.test_execution import FakeRazorpay, allowed_proposal


OWNER = Actor(subject="user_owner", kind="human")
OTHER = Actor(subject="user_other", kind="human")


def _other_mandate(db) -> Mandate:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    values = {
        "id": "mnd_other",
        "created_by_subject": OTHER.subject,
        "instruction_text": "Buy headphones under INR 20,000",
        "hard_constraints": {
            "max_amount_paise": 2_000_000,
            "allowed_currencies": ["INR"],
            "allowed_merchants": ["merchant_demo"],
            "allowed_categories": ["headphones"],
            "allowed_conditions": ["new"],
            "max_quantity": 1,
            "max_executions": 1,
        },
        "semantic_constraints": [],
        "expires_at": now + timedelta(hours=1),
        "version": 1,
        "max_executions": 1,
    }
    signer = SignatureService()
    canonical = canonical_json_bytes(canonical_mandate_payload(values))
    mandate = Mandate(
        **values,
        signed_version=1,
        status="ACTIVE",
        execution_count=0,
        canonical_payload=canonical.decode(),
        payload_hash=payload_sha256(canonical),
        signature=signer.sign(canonical),
        public_key=signer.public_key_pem,
    )
    db.add(mandate)
    db.commit()
    return mandate


def test_other_actor_cannot_read_or_revoke_mandate(db) -> None:
    mandate, _ = allowed_proposal(db)
    mandate.created_by_subject = OWNER.subject
    db.commit()

    assert get_mandate(mandate.id, db, OWNER).id == mandate.id
    for action in (get_mandate, revoke_mandate):
        with pytest.raises(HTTPException) as exc:
            action(mandate.id, db, OTHER)
        assert exc.value.status_code == 403
        assert exc.value.detail["reason_code"] == "RESOURCE_NOT_OWNED"
    assert db.get(Mandate, mandate.id).status == "ACTIVE"


def test_other_actor_cannot_resolve_step_up(db) -> None:
    mandate, proposal = allowed_proposal(db, status="STEP_UP")
    mandate.created_by_subject = OWNER.subject
    step_up = create_step_up(db, proposal, "SEMANTIC_CONTRADICTED", {})
    db.commit()
    adapter = FakeRazorpay()

    assert get_step_up(step_up.id, db, OWNER).id == step_up.id
    with pytest.raises(HTTPException):
        get_step_up(step_up.id, db, OTHER)
    with pytest.raises(HTTPException):
        approve(step_up.id, db, adapter, OTHER)
    with pytest.raises(HTTPException):
        reject(step_up.id, db, OTHER)
    assert step_up.status == "PENDING"
    assert adapter.calls == []


def test_audit_feed_contains_only_owned_authority(db) -> None:
    owned, proposal = allowed_proposal(db)
    owned.created_by_subject = OWNER.subject
    other = _other_mandate(db)
    db.add_all(
        [
            AuditEvent(event_type="OWNED", entity_type="mandate", entity_id=owned.id, payload={}),
            AuditEvent(event_type="OWNED_PROPOSAL", entity_type="proposal", entity_id=proposal.id, payload={}),
            AuditEvent(event_type="OTHER", entity_type="mandate", entity_id=other.id, payload={}),
        ]
    )
    db.commit()

    event_types = {event.event_type for event in list_audit(100, db, OWNER)}
    assert {"OWNED", "OWNED_PROPOSAL"} <= event_types
    assert "OTHER" not in event_types
