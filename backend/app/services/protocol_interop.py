from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from app.db.models import CheckoutProposal, Mandate, Product
from app.services.signature_service import SignatureService, canonical_json_bytes, canonical_mandate_payload, payload_sha256


def export_ap2_mandate(mandate: Mandate) -> dict[str, Any]:
    """Export JANUS signed mandate as a standard AP2 (Agent Payments Protocol v1) Delegation Envelope.
    
    Conforms to the emerging AP2 specification for cryptographic agent authority delegation.
    """
    return {
        "protocol": "AP2/1.0",
        "envelope_type": "agent_delegation_credential",
        "delegation_id": mandate.id,
        "principal": {
            "type": "human_delegator",
            "subject": mandate.created_by_subject or "human_operator",
        },
        "delegatee": {
            "type": "autonomous_shopping_agent",
            "id": "janus_buyer_v1",
            "capabilities": ["catalog_discovery", "intent_matching", "checkout_initiation"],
        },
        "hard_bounds": {
            "max_amount_paise": mandate.hard_constraints.get("max_amount_paise"),
            "currency": mandate.hard_constraints.get("allowed_currencies", ["INR"])[0],
            "allowed_merchants": mandate.hard_constraints.get("allowed_merchants", []),
            "allowed_categories": mandate.hard_constraints.get("allowed_categories", []),
            "allowed_conditions": mandate.hard_constraints.get("allowed_conditions", ["new"]),
            "max_quantity": mandate.hard_constraints.get("max_quantity", 1),
            "max_executions": mandate.max_executions,
        },
        "semantic_intent_clauses": [
            {"clause_id": c.get("id"), "predicate": c.get("text")}
            for c in (mandate.semantic_constraints or [])
        ],
        "state": {
            "status": mandate.status,
            "version": mandate.version,
            "execution_count": mandate.execution_count,
            "expires_at": mandate.expires_at.isoformat(),
        },
        "cryptographic_proof": {
            "algorithm": "ES256",
            "signature_b64": mandate.signature,
            "public_key_pem": mandate.public_key,
            "canonical_payload_sha256": mandate.payload_hash,
        },
        "metadata": {
            "standard": "https://github.com/agent-payments-protocol/spec/v1.0",
            "gateway": "JANUS-Merchant-Authorization-Gateway",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }


def import_ap2_mandate(envelope: dict[str, Any]) -> dict[str, Any]:
    """Ingest external AP2 delegation token into JANUS mandate specification.
    
    Validates:
    - Protocol version
    - Required authority fields
    - Cryptographic signature (if present)
    
    Returns a mandate payload that can be used to create a JANUS mandate.
    """
    if envelope.get("protocol") != "AP2/1.0":
        raise ValueError("Unsupported protocol: expected AP2/1.0")

    hard = envelope.get("hard_bounds", {})
    semantic = envelope.get("semantic_intent_clauses", [])
    
    # Validate required authority fields
    missing_fields = []
    if "max_amount_paise" not in hard or hard["max_amount_paise"] is None:
        missing_fields.append("max_amount_paise")
    if "allowed_categories" not in hard or not hard["allowed_categories"]:
        missing_fields.append("allowed_categories")
    if "allowed_merchants" not in hard or not hard["allowed_merchants"]:
        missing_fields.append("allowed_merchants")
    
    if missing_fields:
        raise ValueError(f"AP2 envelope missing required authority fields: {', '.join(missing_fields)}")
    
    # Verify signature if cryptographic proof is present
    crypto_proof = envelope.get("cryptographic_proof", {})
    if crypto_proof:
        signature_b64 = crypto_proof.get("signature_b64")
        public_key_pem = crypto_proof.get("public_key_pem")
        canonical_hash = crypto_proof.get("canonical_payload_sha256")
        
        if not all([signature_b64, public_key_pem, canonical_hash]):
            raise ValueError("AP2 envelope has incomplete cryptographic proof")
        
        # Reconstruct and verify the payload
        reconstructed_payload = {
            "id": envelope.get("delegation_id"),
            "created_by_subject": envelope.get("principal", {}).get("subject"),
            "instruction_text": f"AP2 Delegated Authority from {envelope.get('principal', {}).get('subject', 'human')}",
            "hard_constraints": {
                "max_amount_paise": hard["max_amount_paise"],
                "allowed_currencies": [hard.get("currency", "INR")],
                "allowed_merchants": hard["allowed_merchants"],
                "allowed_categories": hard["allowed_categories"],
                "allowed_conditions": hard.get("allowed_conditions", ["new"]),
                "max_quantity": hard.get("max_quantity", 1),
                "max_executions": hard.get("max_executions", 1),
            },
            "semantic_constraints": [
                {"id": c.get("clause_id", f"clause_{i}"), "text": c.get("predicate", "")}
                for i, c in enumerate(semantic)
            ],
            "expires_at": envelope.get("state", {}).get("expires_at"),
            "version": envelope.get("state", {}).get("version", 1),
            "max_executions": hard.get("max_executions", 1),
        }
        
        canonical = canonical_json_bytes(canonical_mandate_payload(reconstructed_payload))
        computed_hash = payload_sha256(canonical)
        
        if computed_hash != canonical_hash:
            raise ValueError(f"AP2 signature verification failed: hash mismatch (expected {canonical_hash}, computed {computed_hash})")
        
        if not SignatureService.verify(canonical, signature_b64, public_key_pem):
            raise ValueError("AP2 signature verification failed: invalid signature")
    
    return {
        "instruction_text": f"AP2 Delegated Authority from {envelope.get('principal', {}).get('subject', 'human')}",
        "hard_constraints": {
            "max_amount_paise": hard["max_amount_paise"],
            "allowed_currencies": [hard.get("currency", "INR")],
            "allowed_merchants": hard["allowed_merchants"],
            "allowed_categories": hard["allowed_categories"],
            "allowed_conditions": hard.get("allowed_conditions", ["new"]),
            "max_quantity": hard.get("max_quantity", 1),
            "max_executions": hard.get("max_executions", 1),
        },
        "semantic_constraints": [
            {"id": c.get("clause_id", f"clause_{i}"), "text": c.get("predicate", "")}
            for i, c in enumerate(semantic)
        ],
    }


def export_acp_checkout(proposal: CheckoutProposal, mandate: Mandate, product: Product) -> dict[str, Any]:
    """Export proposal as an ACP (Agentic Commerce Protocol v1) Checkout Intent Object."""
    return {
        "protocol": "ACP/1.0",
        "envelope_type": "agent_checkout_intent",
        "transaction_id": proposal.id,
        "agent_request_id": proposal.agent_request_id,
        "created_at": proposal.created_at.isoformat() if hasattr(proposal, "created_at") and proposal.created_at else datetime.now(timezone.utc).isoformat(),
        "status": proposal.status,
        "mandate_binding": {
            "mandate_id": mandate.id,
            "version": mandate.version,
            "signature": mandate.signature[:24] + "...",
        },
        "merchant": {
            "merchant_id": product.merchant_id,
            "gateway_endpoint": "/api/v1/proposals",
        },
        "items": [
            {
                "product_id": product.id,
                "name": product.name,
                "quantity": proposal.quantity,
                "price_paise": proposal.expected_amount_paise,
                "currency": proposal.currency,
                "category": product.category,
                "attributes": product.attributes,
            }
        ],
        "gateway_decision": proposal.decision,
        "settlement": {
            "provider": "razorpay_test_mode",
            "order_id": proposal.razorpay_order_id,
            "ready_for_capture": proposal.status in {"ORDER_CREATED", "EXECUTED", "PAID"},
        },
    }


def verify_x402_handshake(auth_header: str | None) -> dict[str, Any]:
    """Placeholder for HTTP 402 machine-to-machine payment protocol verification.
    
    NOTE: x402 protocol implementation is out of scope for the current JANUS build.
    This endpoint is reserved for future implementation of the x402 agentic micro-payment protocol.
    Currently returns 501 Not Implemented to indicate this is not yet supported.
    
    Per AGENTS.md scope lock, x402 is a future enhancement and should not be implemented
    until core authorization invariants are fully validated.
    """
    return {
        "status": "NOT_IMPLEMENTED",
        "http_code": 501,
        "detail": "x402 agentic micro-payment protocol is not yet implemented in JANUS.",
        "note": "This feature is reserved for future implementation. Current JANUS authorization uses mandate-based delegation without x402 protocol.",
        "documentation": "See AGENTS.md scope lock section for future roadmap.",
    }
