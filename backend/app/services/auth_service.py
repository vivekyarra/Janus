from __future__ import annotations

import hmac
from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Header, HTTPException
from jwt import PyJWKClient

from app.config import get_settings


@dataclass(frozen=True)
class Actor:
    subject: str
    kind: str


@lru_cache(maxsize=4)
def _jwks_client(issuer: str) -> PyJWKClient:
    return PyJWKClient(f"{issuer.rstrip('/')}/.well-known/jwks.json", cache_keys=True)


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, detail={"reason_code": "AUTHENTICATION_REQUIRED"})
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(401, detail={"reason_code": "AUTHENTICATION_REQUIRED"})
    return token


def _verify_clerk(token: str) -> Actor:
    settings = get_settings()
    issuer = settings.clerk_issuer_url.rstrip("/")
    if not issuer:
        raise HTTPException(503, detail={"reason_code": "IDENTITY_PROVIDER_NOT_CONFIGURED"})
    try:
        signing_key = _jwks_client(issuer).get_signing_key_from_jwt(token)
        claims = jwt.decode(token, signing_key.key, algorithms=["RS256"], issuer=issuer, options={"verify_aud": False, "require": ["exp", "iat", "nbf"]}, leeway=5)
    except jwt.PyJWTError as exc:
        raise HTTPException(401, detail={"reason_code": "SESSION_TOKEN_INVALID"}) from exc
    authorized_parties = {
        settings.clerk_authorized_party,
        settings.clerk_authorized_party.replace("localhost", "127.0.0.1"),
        settings.clerk_authorized_party.replace("127.0.0.1", "localhost"),
    }
    if claims.get("azp") and claims.get("azp") not in authorized_parties:
        raise HTTPException(401, detail={"reason_code": "SESSION_ORIGIN_INVALID"})
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject.startswith("user_"):
        raise HTTPException(401, detail={"reason_code": "SESSION_SUBJECT_INVALID"})
    return Actor(subject=subject, kind="human")


def require_human_actor(authorization: str | None = Header(default=None)) -> Actor:
    settings = get_settings()
    if not settings.auth_required:
        return Actor(subject="local_operator", kind="human")
    token = _bearer(authorization)
    if settings.app_env != "production" and token == "demo_operator":
        return Actor(subject="user_demo_operator", kind="human")
    return _verify_clerk(token)


def require_proposal_actor(authorization: str | None = Header(default=None)) -> Actor:
    settings = get_settings()
    if not settings.auth_required:
        return Actor(subject="local_agent", kind="agent")
    token = _bearer(authorization)
    if settings.app_env != "production" and token == "demo_operator":
        return Actor(subject="user_demo_operator", kind="agent")
    if settings.janus_agent_api_key:
        if hmac.compare_digest(token, settings.janus_agent_api_key):
            return Actor(subject="agent_api_key", kind="agent")
        raise HTTPException(403, detail={"reason_code": "AGENT_CREDENTIAL_REQUIRED"})
    return _verify_clerk(token)


def require_resource_owner(resource_subject: str | None, actor: Actor) -> None:
    """Prevent authenticated humans from operating another human's authority."""
    if not resource_subject or resource_subject != actor.subject:
        raise HTTPException(403, detail={"reason_code": "RESOURCE_NOT_OWNED"})
