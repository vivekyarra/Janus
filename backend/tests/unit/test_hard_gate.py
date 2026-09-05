from datetime import datetime, timedelta, timezone

import pytest

from app.db.models import Mandate, Product
from app.domain.models import ReasonCode
from app.services.hard_gate import evaluate_hard_constraints
from app.services.signature_service import SignatureService, canonical_json_bytes, canonical_mandate_payload, payload_sha256


def make_mandate(**changes) -> Mandate:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    values = {
        "id": "mnd_hard",
        "instruction_text": "Buy noise-cancelling headphones under INR 20,000. Nothing refurbished.",
        "hard_constraints": {"max_amount_paise": 2_000_000, "allowed_currencies": ["INR"], "allowed_merchants": ["merchant_demo"], "allowed_categories": ["headphones"], "allowed_conditions": ["new"], "max_quantity": 1, "max_executions": 1},
        "semantic_constraints": [], "status": "ACTIVE", "version": 1, "signed_version": 1,
        "expires_at": now + timedelta(hours=1), "max_executions": 1, "execution_count": 0,
    }
    values.update(changes)
    signer = SignatureService()
    signed_values = {**values, "version": values["signed_version"]}
    data = canonical_json_bytes(canonical_mandate_payload(signed_values))
    values.update(canonical_payload=data.decode(), payload_hash=payload_sha256(data), signature=signer.sign(data), public_key=signer.public_key_pem)
    return Mandate(**values)


def make_product(**changes) -> Product:
    values = {"id": "prod", "merchant_id": "merchant_demo", "name": "Headphones", "price_paise": 2_000_000, "currency": "INR", "category": "headphones", "condition": "new", "active": True, "attributes": {}}
    values.update(changes)
    return Product(**values)


@pytest.mark.parametrize("product_changes,mandate_changes,quantity,reason", [
    ({"price_paise": 2_000_001}, {}, 1, ReasonCode.AMOUNT_LIMIT_EXCEEDED),
    ({"merchant_id": "liar"}, {}, 1, ReasonCode.MERCHANT_NOT_ALLOWED),
    ({"currency": "USD"}, {}, 1, ReasonCode.CURRENCY_NOT_ALLOWED),
    ({"category": "speakers"}, {}, 1, ReasonCode.CATEGORY_NOT_ALLOWED),
    ({"condition": "refurbished"}, {}, 1, ReasonCode.CONDITION_NOT_ALLOWED),
    ({}, {"expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)}, 1, ReasonCode.MANDATE_EXPIRED),
    ({}, {"status": "REVOKED"}, 1, ReasonCode.MANDATE_REVOKED),
    ({}, {}, 2, ReasonCode.QUANTITY_EXCEEDED),
    ({}, {"status": "CONSUMED"}, 1, ReasonCode.MANDATE_CONSUMED),
    ({}, {"version": 2}, 1, ReasonCode.MANDATE_VERSION_STALE),
])
def test_hard_gate_boundaries(product_changes, mandate_changes, quantity, reason) -> None:
    result = evaluate_hard_constraints(make_mandate(**mandate_changes), make_product(**product_changes), quantity, "req", datetime.now(timezone.utc))
    assert result.status == "FAIL"
    assert result.reason_code == reason


def test_exact_max_amount_passes() -> None:
    result = evaluate_hard_constraints(make_mandate(), make_product(), 1, "req", datetime.now(timezone.utc))
    assert result.status == "PASS"
    assert result.reason_code is None
    assert all(check.passed for check in result.checks)


def test_invalid_signature_fails_first() -> None:
    mandate = make_mandate()
    mandate.signature = "tampered"
    result = evaluate_hard_constraints(mandate, make_product(), 1, "req", datetime.now(timezone.utc))
    assert result.reason_code == ReasonCode.SIGNATURE_INVALID
    assert len(result.checks) == 1
