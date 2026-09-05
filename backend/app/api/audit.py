from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.schemas import AuditRead
from app.db.models import AuditEvent, CheckoutProposal, Mandate, StepUpRequest
from app.db.session import get_db
from app.services.auth_service import Actor, require_human_actor


router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get("", response_model=list[AuditRead])
def list_audit(limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db), actor: Actor = Depends(require_human_actor)):
    owned_mandates = select(Mandate.id).where(Mandate.created_by_subject == actor.subject)
    owned_proposals = select(CheckoutProposal.id).where(CheckoutProposal.mandate_id.in_(owned_mandates))
    owned_step_ups = select(StepUpRequest.id).where(StepUpRequest.proposal_id.in_(owned_proposals))
    query = (
        select(AuditEvent)
        .where(
            or_(
                (AuditEvent.entity_type == "mandate") & AuditEvent.entity_id.in_(owned_mandates),
                (AuditEvent.entity_type == "proposal") & AuditEvent.entity_id.in_(owned_proposals),
                (AuditEvent.entity_type == "step_up") & AuditEvent.entity_id.in_(owned_step_ups),
            )
        )
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
    )
    return list(db.scalars(query))
