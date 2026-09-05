from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from app.services.signature_service import SignatureService, canonical_json_bytes, canonical_mandate_payload


@pytest.fixture
def payload():
    return {
        "id": "mnd_test",
        "instruction_text": "Buy headphones under INR 20,000",
        "hard_constraints": {"max_amount_paise": 2_000_000, "allowed_categories": ["headphones"]},
        "semantic_constraints": [{"id": "travel", "text": "good for travel"}],
        "expires_at": datetime.now(timezone.utc).replace(microsecond=0) + timedelta(hours=1),
        "version": 1,
        "max_executions": 1,
    }


def test_canonical_bytes_stable_across_key_order(payload) -> None:
    reversed_payload = dict(reversed(list(payload.items())))
    assert canonical_json_bytes(canonical_mandate_payload(payload)) == canonical_json_bytes(canonical_mandate_payload(reversed_payload))


@pytest.mark.parametrize("path,value", [("max_amount_paise", 2_000_001), ("allowed_categories", ["speakers"])])
def test_tampering_invalidates_signature(payload, path, value) -> None:
    service = SignatureService()
    original = canonical_json_bytes(canonical_mandate_payload(payload))
    signature = service.sign(original)
    changed = deepcopy(payload)
    changed["hard_constraints"][path] = value
    assert not SignatureService.verify(canonical_json_bytes(canonical_mandate_payload(changed)), signature, service.public_key_pem)


def test_expiry_tampering_and_wrong_key_fail(payload) -> None:
    service = SignatureService()
    original = canonical_json_bytes(canonical_mandate_payload(payload))
    signature = service.sign(original)
    changed = deepcopy(payload)
    changed["expires_at"] += timedelta(seconds=1)
    assert not SignatureService.verify(canonical_json_bytes(canonical_mandate_payload(changed)), signature, service.public_key_pem)
    assert not SignatureService.verify(original, signature, SignatureService().public_key_pem)
    assert SignatureService.verify(original, signature, service.public_key_pem)

