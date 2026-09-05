from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import CompileMandateRequest, CreateMandateRequest
from app.db.models import Mandate, new_id
from app.db.session import get_db
from app.domain.models import MandateDraft, MandateRead
from app.services.audit_service import write_audit
from app.services.intent_compiler import compile_intent
from app.services.revocation_service import revoke_mandate as revoke_mandate_service
from app.services.signature_service import SignatureService, canonical_json_bytes, canonical_mandate_payload, payload_sha256
from app.services.auth_service import Actor, require_human_actor, require_resource_owner


router = APIRouter(prefix="/api/v1/mandates", tags=["mandates"])


@router.post("/compile", response_model=MandateDraft)
def compile_mandate(request: CompileMandateRequest, _: Actor = Depends(require_human_actor)):
    return compile_intent(request.instruction_text, request.merchant_id)


@router.post("", response_model=MandateRead, status_code=201)
def create_mandate(request: CreateMandateRequest, db: Session = Depends(get_db), actor: Actor = Depends(require_human_actor)):
    expires = request.expires_at if request.expires_at.tzinfo else request.expires_at.replace(tzinfo=timezone.utc)
    if expires <= datetime.now(timezone.utc):
        raise HTTPException(422, detail={"reason_code": "MANDATE_EXPIRED"})
    mandate_id = new_id("mnd")
    values = {"id": mandate_id, "created_by_subject": actor.subject, "instruction_text": request.instruction_text, "hard_constraints": request.hard_constraints.model_dump(), "semantic_constraints": [item.model_dump() for item in request.semantic_constraints], "expires_at": expires, "version": 1, "max_executions": request.hard_constraints.max_executions}
    signer = SignatureService()
    canonical = canonical_json_bytes(canonical_mandate_payload(values))
    mandate = Mandate(**values, canonical_payload=canonical.decode(), payload_hash=payload_sha256(canonical), signature=signer.sign(canonical), public_key=signer.public_key_pem, status="ACTIVE", signed_version=1)
    db.add(mandate)
    write_audit(db, "MANDATE_CREATED", "mandate", mandate.id, {"status": "ACTIVE", "version": 1, "actor_subject": actor.subject})
    write_audit(db, "MANDATE_SIGNED", "mandate", mandate.id, {"algorithm": "ES256", "payload_hash": mandate.payload_hash, "signed_fields": list(canonical_mandate_payload(values))})
    db.commit()
    db.refresh(mandate)
    return mandate


@router.get("/{mandate_id}", response_model=MandateRead)
def get_mandate(mandate_id: str, db: Session = Depends(get_db), actor: Actor = Depends(require_human_actor)):
    mandate = db.get(Mandate, mandate_id)
    if mandate is None:
        raise HTTPException(404, detail={"reason_code": "MANDATE_NOT_FOUND"})
    require_resource_owner(mandate.created_by_subject, actor)
    return mandate


@router.post("/{mandate_id}/revoke", response_model=MandateRead)
def revoke_mandate(mandate_id: str, db: Session = Depends(get_db), actor: Actor = Depends(require_human_actor)):
    existing = db.get(Mandate, mandate_id)
    if existing is None:
        raise HTTPException(404, detail={"reason_code": "MANDATE_NOT_FOUND"})
    require_resource_owner(existing.created_by_subject, actor)
    mandate = revoke_mandate_service(db, mandate_id)
    return mandate
