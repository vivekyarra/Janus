import base64
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec


SIGNED_FIELDS = (
    "id",
    "instruction_text",
    "hard_constraints",
    "semantic_constraints",
    "expires_at",
    "version",
    "max_executions",
)


def _normalize(value: Any) -> Any:
    if isinstance(value, datetime):
        aware = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
        normalized = aware.isoformat(timespec="seconds")
        return normalized.replace("+00:00", "Z")
    if isinstance(value, dict):
        return {key: _normalize(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    return value


def canonical_mandate_payload(source: Any) -> dict[str, Any]:
    def read(field: str) -> Any:
        if isinstance(source, dict):
            return source[field]
        if field == "version" and hasattr(source, "signed_version"):
            return source.signed_version
        return getattr(source, field)

    return {field: _normalize(read(field)) for field in SIGNED_FIELDS}


def canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(_normalize(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def payload_sha256(payload_bytes: bytes) -> str:
    return hashlib.sha256(payload_bytes).hexdigest()


class SignatureService:
    def __init__(self, private_key_pem: str = "") -> None:
        if private_key_pem:
            self._private_key = serialization.load_pem_private_key(private_key_pem.encode(), password=None)
        else:
            self._private_key = ec.generate_private_key(ec.SECP256R1())

    @property
    def public_key_pem(self) -> str:
        return self._private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()

    def sign(self, payload_bytes: bytes) -> str:
        signature = self._private_key.sign(payload_bytes, ec.ECDSA(hashes.SHA256()))
        return base64.urlsafe_b64encode(signature).decode()

    @staticmethod
    def verify(payload_bytes: bytes, signature: str, public_key_pem: str) -> bool:
        try:
            public_key = serialization.load_pem_public_key(public_key_pem.encode())
            public_key.verify(base64.urlsafe_b64decode(signature.encode()), payload_bytes, ec.ECDSA(hashes.SHA256()))
            return True
        except (ValueError, TypeError, InvalidSignature):
            return False
