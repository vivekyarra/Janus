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


def test_ap2_import_missing_required_fields() -> None:
    """Test that AP2 import rejects envelopes missing required authority fields."""
    # Missing max_amount_paise
    envelope_missing_amount = {
        "protocol": "AP2/1.0",
        "hard_bounds": {
            "allowed_merchants": ["merchant_demo"],
            "allowed_categories": ["headphones"],
        },
        "semantic_intent_clauses": [],
    }
    with pytest.raises(ValueError, match="missing required authority fields.*max_amount_paise"):
        import_ap2_mandate(envelope_missing_amount)
    
    # Missing allowed_categories
    envelope_missing_categories = {
        "protocol": "AP2/1.0",
        "hard_bounds": {
            "max_amount_paise": 1000000,
            "allowed_merchants": ["merchant_demo"],
        },
        "semantic_intent_clauses": [],
    }
    with pytest.raises(ValueError, match="missing required authority fields.*allowed_categories"):
        import_ap2_mandate(envelope_missing_categories)
    
    # Missing allowed_merchants
    envelope_missing_merchants = {
        "protocol": "AP2/1.0",
        "hard_bounds": {
            "max_amount_paise": 1000000,
            "allowed_categories": ["headphones"],
        },
        "semantic_intent_clauses": [],
    }
    with pytest.raises(ValueError, match="missing required authority fields.*allowed_merchants"):
        import_ap2_mandate(envelope_missing_merchants)


def test_ap2_import_signature_verification() -> None:
    """Test that AP2 import verifies cryptographic signatures when present."""
    signer = SignatureService()
    
    # Create a valid AP2 envelope with signature
    valid_envelope = {
        "protocol": "AP2/1.0",
        "delegation_id": "test_del_001",
        "principal": {"subject": "test_human"},
        "hard_bounds": {
            "max_amount_paise": 1000000,
            "allowed_merchants": ["merchant_demo"],
            "allowed_categories": ["headphones"],
        },
        "semantic_intent_clauses": [],
        "state": {
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "version": 1,
        },
    }
    
    # Sign it
    payload = {
        "id": "test_del_001",
        "created_by_subject": "test_human",
        "instruction_text": "AP2 Delegated Authority from test_human",
        "hard_constraints": {
            "max_amount_paise": 1000000,
            "allowed_currencies": ["INR"],
            "allowed_merchants": ["merchant_demo"],
            "allowed_categories": ["headphones"],
            "allowed_conditions": ["new"],
            "max_quantity": 1,
            "max_executions": 1,
        },
        "semantic_constraints": [],
        "expires_at": valid_envelope["state"]["expires_at"],
        "version": 1,
        "max_executions": 1,
    }
    
    canonical = canonical_json_bytes(canonical_mandate_payload(payload))
    signature = signer.sign(canonical)
    hash_value = payload_sha256(canonical)
    
    valid_envelope["cryptographic_proof"] = {
        "algorithm": "ES256",
        "signature_b64": signature,
        "public_key_pem": signer.public_key_pem,
        "canonical_payload_sha256": hash_value,
    }
    
    # Should succeed with valid signature
    imported = import_ap2_mandate(valid_envelope)
    assert imported["hard_constraints"]["max_amount_paise"] == 1000000
    
    # Should fail with invalid signature
    invalid_envelope = valid_envelope.copy()
    invalid_envelope["cryptographic_proof"] = valid_envelope["cryptographic_proof"].copy()
    invalid_envelope["cryptographic_proof"]["signature_b64"] = "invalid_signature_base64"
    
    with pytest.raises(ValueError, match="signature verification failed"):
        import_ap2_mandate(invalid_envelope)
    
    # Should fail with hash mismatch
    hash_mismatch_envelope = valid_envelope.copy()
    hash_mismatch_envelope["cryptographic_proof"] = valid_envelope["cryptographic_proof"].copy()
    hash_mismatch_envelope["cryptographic_proof"]["canonical_payload_sha256"] = "wrong_hash"
    
    with pytest.raises(ValueError, match="hash mismatch"):
        import_ap2_mandate(hash_mismatch_envelope)
    
    # Should fail with incomplete cryptographic proof
    incomplete_proof_envelope = valid_envelope.copy()
    incomplete_proof_envelope["cryptographic_proof"] = {
        "signature_b64": signature,
        # Missing public_key_pem and canonical_payload_sha256
    }
    
    with pytest.raises(ValueError, match="incomplete cryptographic proof"):
        import_ap2_mandate(incomplete_proof_envelope)


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


def test_x402_handshake_not_implemented() -> None:
    """Test that x402 verification returns 501 Not Implemented as per scope lock."""
    # x402 is not implemented per AGENTS.md scope lock
    result = verify_x402_handshake(None)
    assert result["http_code"] == 501
    assert result["status"] == "NOT_IMPLEMENTED"
    assert "not yet implemented" in result["detail"].lower()
    
    # Even with a valid header, it should return 501
    result_with_header = verify_x402_handshake("X402 token_abc123_signature")
    assert result_with_header["http_code"] == 501
    assert result_with_header["status"] == "NOT_IMPLEMENTED"


def test_interop_api_endpoints(db, test_mandate) -> None:
    from app.db.session import get_db

    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            resp = client.get(f"/api/v1/interop/ap2/{test_mandate.id}")
            assert resp.status_code == 200
            assert resp.json()["protocol"] == "AP2/1.0"

            # x402 endpoint returns 501 Not Implemented
            resp_501 = client.post("/api/v1/interop/x402/verify")
            assert resp_501.status_code == 501
            assert resp_501.json()["status"] == "NOT_IMPLEMENTED"

            # Even with authorization header, still returns 501
            resp_501_with_header = client.post("/api/v1/interop/x402/verify", headers={"Authorization": "X402 test_valid_token"})
            assert resp_501_with_header.status_code == 501
            assert resp_501_with_header.json()["status"] == "NOT_IMPLEMENTED"
    finally:
        app.dependency_overrides.clear()
