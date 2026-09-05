from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.api.dependencies import get_semantic_model
from app.db.models import AuditEvent, Product, StepUpRequest
from app.db.session import get_db
from app.main import app
from app.repositories.catalog import seed_catalog
from tests.adversarial.test_semantic_safety import ScriptedModel


def create_mandate(client, semantic=None):
    response = client.post("/api/v1/mandates", json={"instruction_text": "Buy headphones under INR 20,000. Nothing flashy.", "hard_constraints": {"max_amount_paise": 2000000, "allowed_currencies": ["INR"], "allowed_merchants": ["merchant_demo"], "allowed_categories": ["headphones"], "allowed_conditions": ["new"], "max_quantity": 1, "max_executions": 1}, "semantic_constraints": semantic or [], "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()})
    assert response.status_code == 201
    return response.json()


def proposal(client, mandate, product_id="prod_a", version=1, request_id="decision-1"):
    return client.post("/api/v1/proposals", json={"mandate_id": mandate["id"], "mandate_version": version, "product_id": product_id, "quantity": 1, "agent_request_id": request_id})


def test_semantic_contradiction_creates_bound_step_up(db) -> None:
    seed_catalog(db)
    model = ScriptedModel({"results": [{"constraint_id": "not_flashy", "status": "CONTRADICTED", "evidence_fields": ["color", "branding"], "reason": "Explicitly flashy."}]})
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_semantic_model] = lambda: model
    try:
        with TestClient(app) as client:
            mandate = create_mandate(client, [{"id": "not_flashy", "text": "nothing flashy"}])
            response = proposal(client, mandate, "prod_d")
            assert response.status_code == 201
            result = response.json()["decision"]
            assert result["decision"] == "STEP_UP"
            assert result["reason_code"] == "SEMANTIC_CONTRADICTED"
            assert db.get(StepUpRequest, result["step_up_id"]).proposal_id == result["proposal_id"]
            assert db.query(AuditEvent).filter_by(event_type="STEP_UP_REQUESTED").count() == 1
    finally:
        app.dependency_overrides.clear()


def test_semantic_unknown_creates_step_up(db) -> None:
    seed_catalog(db)
    model = ScriptedModel({"results": [{"constraint_id": "travel", "status": "INSUFFICIENT_EVIDENCE", "evidence_fields": [], "reason": "No travel evidence."}]})
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_semantic_model] = lambda: model
    try:
        with TestClient(app) as client:
            mandate = create_mandate(client, [{"id": "travel", "text": "good for travel"}])
            result = proposal(client, mandate, "prod_e").json()["decision"]
            assert result["decision"] == "STEP_UP"
            assert result["reason_code"] == "SEMANTIC_INSUFFICIENT_EVIDENCE"
    finally:
        app.dependency_overrides.clear()


def test_inactive_product_and_stale_version_block(db) -> None:
    seed_catalog(db)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_semantic_model] = lambda: ScriptedModel({"results": []})
    try:
        with TestClient(app) as client:
            mandate = create_mandate(client)
            product = db.get(Product, "prod_a")
            product.active = False
            db.commit()
            inactive = proposal(client, mandate, request_id="inactive-1").json()["decision"]
            assert inactive["decision"] == "BLOCK"
            assert inactive["reason_code"] == "PRODUCT_INACTIVE"
            product.active = True
            db.commit()
            stale = proposal(client, mandate, version=2, request_id="stale-1").json()["decision"]
            assert stale["decision"] == "BLOCK"
            assert stale["reason_code"] == "MANDATE_VERSION_STALE"
    finally:
        app.dependency_overrides.clear()
