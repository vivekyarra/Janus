from datetime import datetime, timedelta, timezone

from app.db.models import Mandate, new_id
from app.domain.models import HardConstraints, MandateDraft
from app.repositories.catalog import seed_catalog
from app.services.auth_service import Actor
from app.services.buyer_agent import AutonomousBuyerAgent
from app.services.intent_compiler import compile_intent
from app.services.signature_service import (
    SignatureService,
    canonical_json_bytes,
    canonical_mandate_payload,
    payload_sha256,
)


def _create_test_mandate(db, draft: MandateDraft, expires_at: datetime, signer: SignatureService) -> Mandate:
    values = {
        "id": new_id("mnd"),
        "created_by_subject": "test_human",
        "instruction_text": draft.instruction_text,
        "hard_constraints": draft.hard_constraints.model_dump(),
        "semantic_constraints": [item.model_dump() if hasattr(item, "model_dump") else item for item in draft.semantic_constraints],
        "expires_at": expires_at,
        "version": 1,
        "max_executions": draft.hard_constraints.max_executions,
    }
    canonical = canonical_json_bytes(canonical_mandate_payload(values))
    mandate = Mandate(
        **values,
        canonical_payload=canonical.decode(),
        payload_hash=payload_sha256(canonical),
        signature=signer.sign(canonical),
        public_key=signer.public_key_pem,
        status="ACTIVE",
        signed_version=1,
    )
    db.add(mandate)
    db.commit()
    db.refresh(mandate)
    return mandate


class MockSemanticModel:
    def classify(self, *, instruction: str, constraints: list[dict], evidence: dict) -> dict:
        results = []
        for c in constraints:
            cid = c.get("id", "")
            if "travel" in cid:
                results.append({"constraint_id": cid, "status": "SUPPORTED", "evidence_fields": ["foldable", "travel_case"], "reason": "Verified travel attributes"})
            elif "not_flashy" in cid or "flashy" in cid:
                results.append({"constraint_id": cid, "status": "SUPPORTED", "evidence_fields": ["branding"], "reason": "Minimal branding"})
            else:
                results.append({"constraint_id": cid, "status": "SUPPORTED", "evidence_fields": list(evidence.keys())[:1], "reason": "Supported by evidence"})
        return {"results": results}


class MockRazorpay:
    def __init__(self):
        self.orders = []
        self.public_key_id = "rzp_test_mock"

    def create_order(self, *, amount: int, currency: str, receipt: str, notes: dict) -> dict:
        order = {"id": f"order_{len(self.orders)+1}", "amount": amount, "currency": currency, "receipt": receipt, "status": "created"}
        self.orders.append(order)
        return order

    def fetch_order(self, order_id: str) -> dict:
        return {"id": order_id, "status": "created"}


def test_autonomous_buyer_agent_selects_optimal_product_and_executes(db):
    seed_catalog(db)
    signer = SignatureService()
    now = datetime.now(timezone.utc).replace(microsecond=0)

    # Issue a signed active mandate
    draft = MandateDraft(
        instruction_text="Buy headphones under INR 20,000 suitable for travel, nothing flashy.",
        hard_constraints=HardConstraints(
            max_amount_paise=2000000,
            allowed_currencies=["INR"],
            allowed_merchants=["merchant_demo"],
            allowed_categories=["headphones"],
            allowed_conditions=["new"],
            max_quantity=1,
            max_executions=1,
        ),
        semantic_constraints=[{"id": "travel", "text": "suitable for travel"}, {"id": "not_flashy", "text": "nothing flashy"}],
    )
    mandate = _create_test_mandate(db, draft, expires_at=now + timedelta(days=1), signer=signer)

    # Run Autonomous Buyer Agent
    agent = AutonomousBuyerAgent(
        db=db,
        semantic_model=MockSemanticModel(),
        razorpay=MockRazorpay(),
        actor=Actor(subject="test_agent", kind="agent"),
    )

    response = agent.run(mandate_id=mandate.id, merchant_id="merchant_demo", auto_execute=True)

    assert response.status in {"ORDER_CREATED", "EXECUTED", "ALLOWED"}
    assert response.decision == "ALLOW"
    assert response.selected_product_id == "prod_a"  # Sony Voyager NC ₹18,499
    assert response.razorpay_order_id is not None
    assert len(response.steps) >= 5
    assert len(response.candidates_evaluated) == 6

    # Check that Sony Studio Pro (₹21,499) was rejected for exceeding budget
    studio_eval = next(c for c in response.candidates_evaluated if c.product_id == "prod_b")
    assert studio_eval.hard_eligible is False
    assert "Exceeds budget" in studio_eval.rejection_reason


def test_autonomous_buyer_agent_halts_safely_when_no_product_eligible(db):
    seed_catalog(db)
    signer = SignatureService()
    now = datetime.now(timezone.utc).replace(microsecond=0)

    # Mandate with budget of ₹5,000 (all catalog products exceed ₹5,000 except none)
    draft = MandateDraft(
        instruction_text="Budget is ₹5,000 only.",
        hard_constraints=HardConstraints(
            max_amount_paise=500000,
            allowed_currencies=["INR"],
            allowed_merchants=["merchant_demo"],
            allowed_categories=["headphones"],
            allowed_conditions=["new"],
            max_quantity=1,
            max_executions=1,
        ),
        semantic_constraints=[],
    )
    mandate = _create_test_mandate(db, draft, expires_at=now + timedelta(days=1), signer=signer)

    agent = AutonomousBuyerAgent(
        db=db,
        semantic_model=MockSemanticModel(),
        razorpay=MockRazorpay(),
        actor=Actor(subject="test_agent", kind="agent"),
    )

    response = agent.run(mandate_id=mandate.id, merchant_id="merchant_demo", auto_execute=True)

    assert response.decision == "BLOCK"
    assert response.selected_product_id is None
    assert response.razorpay_order_id is None
    assert any("violate human spending limits" in s.detail for s in response.steps)
