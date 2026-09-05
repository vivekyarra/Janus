from types import SimpleNamespace
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from app.config import Settings, validate_production_settings
from app.services import auth_service


def token_for(private_key, *, issuer="https://identity.example", azp="https://merchant.example", sub="user_real") -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"iss": issuer, "azp": azp, "sub": sub, "iat": now, "nbf": now, "exp": now + timedelta(minutes=5)}, private_key, algorithm="RS256", headers={"kid": "test"})


def test_clerk_session_is_bound_to_issuer_origin_and_human_subject(monkeypatch) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    settings = Settings(auth_required=True, clerk_issuer_url="https://identity.example", clerk_authorized_party="https://merchant.example")
    monkeypatch.setattr(auth_service, "get_settings", lambda: settings)
    monkeypatch.setattr(auth_service, "_jwks_client", lambda _: SimpleNamespace(get_signing_key_from_jwt=lambda __: SimpleNamespace(key=private_key.public_key())))
    actor = auth_service._verify_clerk(token_for(private_key))
    assert (actor.subject, actor.kind) == ("user_real", "human")
    with pytest.raises(HTTPException) as exc:
        auth_service._verify_clerk(token_for(private_key, azp="https://attacker.example"))
    assert exc.value.detail["reason_code"] == "SESSION_ORIGIN_INVALID"


def test_agent_key_is_separate_and_constant_time_path(monkeypatch) -> None:
    settings = Settings(auth_required=True, janus_agent_api_key="a" * 32, clerk_issuer_url="https://identity.example")
    monkeypatch.setattr(auth_service, "get_settings", lambda: settings)
    assert auth_service.require_proposal_actor("Bearer " + "a" * 32).kind == "agent"
    with pytest.raises(HTTPException):
        auth_service.require_human_actor("Bearer " + "a" * 32)
    with pytest.raises(HTTPException) as exc:
        auth_service.require_proposal_actor("Bearer human-clerk-session")
    assert exc.value.status_code == 403
    assert exc.value.detail["reason_code"] == "AGENT_CREDENTIAL_REQUIRED"


def test_production_configuration_fails_closed() -> None:
    with pytest.raises(RuntimeError) as exc:
        validate_production_settings(Settings(app_env="production"))
    assert "PostgreSQL" in str(exc.value)
    valid = Settings(app_env="production", database_url="postgresql+psycopg://db/janus", auth_required=True, clerk_issuer_url="https://identity.example", clerk_authorized_party="https://merchant.example", janus_agent_api_key="a" * 32, razorpay_key_id="rzp_test_valid", razorpay_key_secret="secret", gemini_api_key="test-key")
    validate_production_settings(valid)
