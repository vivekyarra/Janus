from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from sqlalchemy import select

from app.db.models import AuditEvent, CheckoutProposal, Mandate, Product
from app.domain.models import (
    HardConstraints,
    MandateDraft,
    SemanticConstraint,
)
from app.integrations.llm_adapter import SemanticModelPort
from app.integrations.razorpay_adapter import RazorpayPort
from app.services.auth_service import Actor
from app.services.buyer_agent import AutonomousBuyerAgent
from app.services.payment_service import verify_checkout_payment
from app.services.signature_service import (
    SignatureService,
    canonical_json_bytes,
    canonical_mandate_payload,
    payload_sha256,
)


class KillerTestSemanticModel(SemanticModelPort):
    """Accurately classifies candidate evidence:

    - prod_killer_a: SUPPORTED for both travel and not_flashy
    - prod_killer_c: CONTRADICTED for not_flashy (gold finish, oversized branding)
    """

    def classify(
        self,
        *,
        instruction: str,
        constraints: list[dict],
        evidence: dict[str, Any],
    ) -> dict[str, Any]:
        results = []
        for c in constraints:
            c_id = c["id"]
            if c_id == "not_flashy":
                branding = str(evidence.get("branding", "")).lower()
                color = str(evidence.get("color", "")).lower()
                if "oversized" in branding or "gold" in color or "metallic" in color:
                    results.append(
                        {
                            "constraint_id": "not_flashy",
                            "status": "CONTRADICTED",
                            "evidence_fields": ["branding", "color"],
                            "reason": "Oversized branding and metallic gold finish directly contradict the instruction 'nothing flashy'.",
                        }
                    )
                else:
                    results.append(
                        {
                            "constraint_id": "not_flashy",
                            "status": "SUPPORTED",
                            "evidence_fields": ["branding", "color"],
                            "reason": "Minimal branding and matte black finish align with 'nothing flashy'.",
                        }
                    )
            elif c_id == "travel":
                if evidence.get("foldable") and evidence.get("travel_case"):
                    results.append(
                        {
                            "constraint_id": "travel",
                            "status": "SUPPORTED",
                            "evidence_fields": ["foldable", "travel_case"],
                            "reason": "Foldable hinge and included travel case satisfy travel requirement.",
                        }
                    )
                else:
                    results.append(
                        {
                            "constraint_id": "travel",
                            "status": "INSUFFICIENT_EVIDENCE",
                            "evidence_fields": [],
                            "reason": "Missing travel evidence.",
                        }
                    )
            else:
                results.append(
                    {
                        "constraint_id": c_id,
                        "status": "SUPPORTED",
                        "evidence_fields": list(evidence.keys())[:1],
                        "reason": "Constraint supported by catalog evidence.",
                    }
                )
        return {"results": results}


class KillerTestRazorpay(RazorpayPort):
    def __init__(self) -> None:
        self.orders: list[dict[str, Any]] = []
        self.payment: dict[str, Any] = {
            "id": "pay_killer001",
            "order_id": "order_killer_001",
            "amount": 1499900,
            "currency": "INR",
            "status": "captured",
        }

    @property
    def public_key_id(self) -> str:
        return "rzp_test_fixture_key"

    def create_order(
        self,
        *,
        amount: int,
        currency: str,
        receipt: str,
        notes: dict[str, str],
    ) -> dict[str, Any]:
        order = {
            "id": "order_killer_001",
            "entity": "order",
            "amount": amount,
            "currency": currency,
            "receipt": receipt,
            "status": "created",
            "notes": notes,
        }
        self.orders.append(order)
        return order

    def fetch_payment(self, payment_id: str) -> dict[str, Any]:
        return self.payment


def test_the_killer_scenario_end_to_end(db) -> None:
    """THE KILLER TEST:

    Mandate: 'Buy premium noise-cancelling headphones under INR 20,000 for travel. Nothing flashy.'
    Merchant Catalog:
      - Product B (₹21,499): Studio Master Pro -> Hard-blocked (AMOUNT_LIMIT_EXCEEDED)
      - Product C (₹18,999): Glamour Gold Party -> Semantic-rejected (CONTRADICTED: flashy gold)
      - Product A (₹14,999): AeroTravel ANC-450 -> Selected, cleared, Razorpay test order created

    Followed by:
      - Payment verification with valid signature + provider facts
      - Immutable audit trail explaining every decision
    """
    # 1. Seed merchant catalog with the 3 canonical candidate products
    prod_a = Product(
        id="prod_killer_a",
        merchant_id="northstar_audio",
        name="AeroTravel ANC-450",
        price_paise=1499900,  # ₹14,999
        currency="INR",
        category="headphones",
        condition="new",
        active=True,
        attributes={
            "foldable": True,
            "travel_case": True,
            "noise_cancelling": True,
            "branding": "minimal",
            "color": "matte black",
            "weight_g": 240,
        },
    )
    prod_b = Product(
        id="prod_killer_b",
        merchant_id="northstar_audio",
        name="Studio Master Flagship",
        price_paise=2149900,  # ₹21,499 -> Exceeds ₹20,000 budget!
        currency="INR",
        category="headphones",
        condition="new",
        active=True,
        attributes={
            "foldable": True,
            "travel_case": True,
            "noise_cancelling": True,
            "branding": "minimal",
            "color": "graphite",
            "weight_g": 310,
        },
    )
    prod_c = Product(
        id="prod_killer_c",
        merchant_id="northstar_audio",
        name="Glamour Gold Party Edition",
        price_paise=1899900,  # ₹18,999 -> Within budget, but flashy!
        currency="INR",
        category="headphones",
        condition="new",
        active=True,
        attributes={
            "foldable": True,
            "travel_case": True,
            "noise_cancelling": True,
            "branding": "oversized metallic logo",
            "color": "metallic gold",
            "collection": "party edition",
            "weight_g": 280,
        },
    )
    db.add_all([prod_a, prod_b, prod_c])
    db.commit()

    # 2. Issue and sign the human mandate
    now = datetime.now(timezone.utc).replace(microsecond=0)
    signer = SignatureService()
    mandate_values = {
        "id": "mnd_killer_001",
        "instruction_text": "Buy premium noise-cancelling headphones under INR 20,000 for travel. Nothing flashy.",
        "hard_constraints": {
            "max_amount_paise": 2000000,  # ₹20,000 ceiling
            "allowed_currencies": ["INR"],
            "allowed_merchants": ["northstar_audio"],
            "allowed_categories": ["headphones"],
            "allowed_conditions": ["new"],
            "max_quantity": 1,
            "max_executions": 1,
        },
        "semantic_constraints": [
            {"id": "travel", "text": "good for travel"},
            {"id": "not_flashy", "text": "nothing flashy"},
        ],
        "expires_at": now + timedelta(days=2),
        "version": 1,
        "max_executions": 1,
    }
    signed_values = {**mandate_values, "version": mandate_values["version"]}
    canonical = canonical_json_bytes(canonical_mandate_payload(signed_values))
    mandate = Mandate(
        **mandate_values,
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

    # 3. Autonomous Buyer Agent executes shopping cycle
    razorpay = KillerTestRazorpay()
    agent = AutonomousBuyerAgent(
        db=db,
        semantic_model=KillerTestSemanticModel(),
        razorpay=razorpay,
        actor=Actor(subject="agent_autobuyer_001", kind="agent"),
    )

    response = agent.run(mandate_id=mandate.id, merchant_id="northstar_audio", auto_execute=True)

    # 4. Verify candidate evaluations
    evals = {c.product_id: c for c in response.candidates_evaluated}
    assert len(evals) == 3

    # Product B: Hard-blocked on budget limit
    assert evals["prod_killer_b"].hard_eligible is False
    assert "Exceeds budget" in evals["prod_killer_b"].rejection_reason

    # Product C: Passed hard gate, but contradicted semantically
    assert evals["prod_killer_c"].hard_eligible is True
    assert "CONTRADICTED" in evals["prod_killer_c"].semantic_notes

    # Product A: Passed hard gate and fully SUPPORTED semantically
    assert evals["prod_killer_a"].hard_eligible is True
    assert "SUPPORTED" in evals["prod_killer_a"].semantic_notes

    # Verify Agent Selection & Gateway Clearance
    assert response.selected_product_id == "prod_killer_a"
    assert response.decision == "ALLOW"
    assert response.razorpay_order_id == "order_killer_001"
    assert response.amount_paise == 1499900
    assert response.status == "ORDER_CREATED"
    assert len(razorpay.orders) == 1

    # 5. Execute Payment Verification (Server-Side Razorpay Signature & State)
    key_secret = "test_razorpay_secret_key"
    msg = f"{response.razorpay_order_id}|pay_killer001".encode()
    signature = hmac.new(key_secret.encode(), msg, hashlib.sha256).hexdigest()

    verification = verify_checkout_payment(
        db,
        response.proposal_id,
        razorpay_order_id=response.razorpay_order_id,
        razorpay_payment_id="pay_killer001",
        razorpay_signature=signature,
        key_secret=key_secret,
        razorpay=razorpay,
    )
    assert verification["status"] == "VERIFIED"
    assert verification["idempotent_replay"] is False

    # Proposal state is now PAID
    proposal = db.get(CheckoutProposal, response.proposal_id)
    assert proposal.status == "PAID"
    assert proposal.payment_status == "VERIFIED"
    assert proposal.razorpay_payment_id == "pay_killer001"
    assert proposal.paid_at is not None

    # Mandate is consumed (1/1 executions used)
    m = db.get(Mandate, mandate.id)
    assert m.status == "CONSUMED"
    assert m.execution_count == 1

    # 6. Verify Complete, Explainable Audit Trail
    events = list(
        db.scalars(
            select(AuditEvent)
            .where(AuditEvent.entity_id.in_([mandate.id, proposal.id]))
            .order_by(AuditEvent.created_at)
        )
    )
    event_types = [e.event_type for e in events]

    assert "PROPOSAL_RECEIVED" in event_types
    assert "HARD_GATE_PASSED" in event_types
    assert "SEMANTIC_ASSESSMENT_COMPLETED" in event_types
    assert "FINAL_DECISION" in event_types
    assert "EXECUTION_RESERVED" in event_types
    assert "RAZORPAY_ORDER_CREATED" in event_types
    assert "RAZORPAY_PAYMENT_VERIFIED" in event_types

    # Verify audit payload transparency
    final_dec = next(e for e in events if e.event_type == "FINAL_DECISION")
    assert final_dec.payload["decision"] == "ALLOW"
    assert final_dec.payload["razorpay_called"] is False

    order_event = next(e for e in events if e.event_type == "RAZORPAY_ORDER_CREATED")
    assert order_event.payload["razorpay_order_id"] == "order_killer_001"
    assert order_event.payload["amount"] == 1499900
    assert order_event.payload["razorpay_called"] is True

    verify_event = next(e for e in events if e.event_type == "RAZORPAY_PAYMENT_VERIFIED")
    assert verify_event.payload["razorpay_payment_id"] == "pay_killer001"
    assert verify_event.payload["provider_status"] == "captured"
