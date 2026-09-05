from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.db.models import CheckoutProposal, Mandate, Product
from app.main import app
from app.repositories.catalog import seed_catalog
from app.services.protocol_interop import (
    export_acp_checkout,
    export_ap2_mandate,
    import_ap2_mandate,
    verify_x402_handshake,
)
from app.services.signature_service import (
    SignatureService,
    canonical_json_bytes,
    canonical_mandate_payload,
    payload_sha256,
)


@pytest.fixture
def test_mandate(db):
    seed_catalog(db)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    values = {
        "id": "mnd_interop_001",
        "instruction_text": "Buy ANC travel headphones under INR 15,000",
        "hard_constraints": {
            "max_amount_paise": 1_500_000,
            "allowed_currencies": ["INR"],
            "allowed_merchants": ["merchant_demo"],
            "allowed_categories": ["headphones"],
            "allowed_conditions": ["new"],
            "max_quantity": 1,
            "max_executions": 1,
        },
        "semantic_constraints": [{"id": "travel", "text": "good for travel"}],
        "expires_at": now + timedelta(hours=2),
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


def test_export_and_import_ap2_envelope(test_mandate) -> None:
    ap2 = export_ap2_mandate(test_mandate)
    assert ap2["protocol"] == "AP2/1.0"
    assert ap2["envelope_type"] == "agent_delegation_credential"
    assert ap2["delegation_id"] == test_mandate.id
    assert ap2["hard_bounds"]["max_amount_paise"] == 1_500_000
    assert ap2["cryptographic_proof"]["algorithm"] == "ES256"

    imported = import_ap2_mandate(ap2)
    assert imported["hard_constraints"]["max_amount_paise"] == 1_500_000
    assert imported["semantic_constraints"][0]["id"] == "travel"


def test_export_acp_checkout_intent(db, test_mandate) -> None:
    product = db.get(Product, "prod_a")
    proposal = CheckoutProposal(
        id="prp_acp_001",
        mandate_id=test_mandate.id,
        mandate_version=1,
        product_id=product.id,
        quantity=1,
        agent_request_id="acp-req-1",
        expected_amount_paise=product.price_paise,
        currency="INR",
        status="ORDER_CREATED",
        decision={"decision": "ALLOW"},
        razorpay_order_id="order_acp_test_123",
    )
    db.add(proposal)
    db.commit()

    acp = export_acp_checkout(proposal, test_mandate, product)
    assert acp["protocol"] == "ACP/1.0"
    assert acp["transaction_id"] == "prp_acp_001"
    assert acp["settlement"]["order_id"] == "order_acp_test_123"
    assert acp["settlement"]["ready_for_capture"] is True


def test_x402_handshake() -> None:
    # Missing header -> 402 Payment Required
    unauth = verify_x402_handshake(None)
    assert unauth["http_code"] == 402
    assert unauth["status"] == "PAYMENT_REQUIRED"

    # Valid X402 header -> 200 Authorized
    auth = verify_x402_handshake("X402 token_abc123_signature")
    assert auth["http_code"] == 200
    assert auth["status"] == "AUTHORIZED"


def test_interop_api_endpoints(db, test_mandate) -> None:
    from app.db.session import get_db

    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            resp = client.get(f"/api/v1/interop/ap2/{test_mandate.id}")
            assert resp.status_code == 200
            assert resp.json()["protocol"] == "AP2/1.0"

            resp_402 = client.post("/api/v1/interop/x402/verify")
            assert resp_402.status_code == 402

            resp_200 = client.post("/api/v1/interop/x402/verify", headers={"Authorization": "X402 test_valid_token"})
            assert resp_200.status_code == 200
            assert resp_200.json()["status"] == "AUTHORIZED"
    finally:
        app.dependency_overrides.clear()
