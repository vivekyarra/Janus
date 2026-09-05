from datetime import datetime, timedelta, timezone

from app.db.models import AuditEvent, CheckoutProposal, Mandate, StepUpRequest
from app.repositories.catalog import seed_catalog


def test_seed_catalog_is_deterministic(db) -> None:
    assert seed_catalog(db) == 5
    assert seed_catalog(db) == 5
    assert db.query(type(db.get_bind().mapper_registry) if False else Mandate).count() == 0
    assert db.execute(__import__("sqlalchemy").text("SELECT count(*) FROM products")).scalar_one() == 5


def test_core_entities_persist(db) -> None:
    seed_catalog(db)
    mandate = Mandate(
        instruction_text="Buy headphones under INR 20,000",
        hard_constraints={"max_amount_paise": 2_000_000},
        semantic_constraints=[],
        canonical_payload="{}",
        payload_hash="0" * 64,
        signature="sig",
        public_key="key",
        status="ACTIVE",
        version=1,
        signed_version=1,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        max_executions=1,
    )
    db.add(mandate)
    db.flush()
    proposal = CheckoutProposal(mandate_id=mandate.id, mandate_version=1, product_id="prod_a", quantity=1, agent_request_id="agent-1", expected_amount_paise=1849900, currency="INR")
    db.add(proposal)
    db.flush()
    step_up = StepUpRequest(proposal_id=proposal.id, binding_hash="1" * 64, reason_code="SEMANTIC_CONTRADICTED", evidence={})
    audit = AuditEvent(event_type="PROPOSAL_RECEIVED", entity_type="proposal", entity_id=proposal.id, payload={"quantity": 1})
    db.add_all([step_up, audit])
    db.commit()
    assert db.get(Mandate, mandate.id).status == "ACTIVE"
    assert db.get(CheckoutProposal, proposal.id).step_up.id == step_up.id
    assert db.query(AuditEvent).one().event_type == "PROPOSAL_RECEIVED"
