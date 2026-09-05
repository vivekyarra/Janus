from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.api.dependencies import get_razorpay_adapter, get_semantic_model
from app.db.session import get_db
from app.main import app
from app.repositories.catalog import seed_catalog
from tests.adversarial.test_semantic_safety import ScriptedModel
from tests.integration.test_execution import FakeRazorpay


def test_same_agent_request_x20_creates_one_proposal_and_one_order(db) -> None:
    seed_catalog(db)
    razorpay = FakeRazorpay()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_razorpay_adapter] = lambda: razorpay
    app.dependency_overrides[get_semantic_model] = lambda: ScriptedModel({"results": []})
    try:
        with TestClient(app) as client:
            mandate_response = client.post("/api/v1/mandates", json={"instruction_text": "Buy headphones under INR 20,000", "hard_constraints": {"max_amount_paise": 2000000, "allowed_currencies": ["INR"], "allowed_merchants": ["merchant_demo"], "allowed_categories": ["headphones"], "allowed_conditions": ["new"], "max_quantity": 1, "max_executions": 1}, "semantic_constraints": [], "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()})
            assert mandate_response.status_code == 201
            mandate = mandate_response.json()
            body = {"mandate_id": mandate["id"], "mandate_version": 1, "product_id": "prod_a", "quantity": 1, "agent_request_id": "agent-replay-001"}
            results = [client.post("/api/v1/proposals", json=body) for _ in range(20)]
            assert results[0].status_code == 201
            assert results[0].json()["decision"]["decision"] == "ALLOW"
            assert all(item.json()["proposal_id"] == results[0].json()["proposal_id"] for item in results)
            assert sum(item.json()["decision"]["reason_code"] == "DUPLICATE_REQUEST" for item in results) == 19
            proposal_id = results[0].json()["proposal_id"]
            executions = [client.post(f"/api/v1/proposals/{proposal_id}/execute") for _ in range(20)]
            assert all(item.status_code == 200 for item in executions)
            assert len(razorpay.calls) == 1
            assert len({item.json()["razorpay_order_id"] for item in executions}) == 1
    finally:
        app.dependency_overrides.clear()
