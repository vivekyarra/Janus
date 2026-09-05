import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CheckoutProposal, StepUpRequest
from app.domain.errors import AuthorizationDenied
from app.integrations.razorpay_adapter import RazorpayPort
from app.services.audit_service import write_audit
from app.services.execution_service import ExecutionService


def proposal_binding(proposal: CheckoutProposal) -> str:
    payload = {"mandate_id": proposal.mandate_id, "proposal_id": proposal.id, "product_id": proposal.product_id, "amount": proposal.expected_amount_paise}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def create_step_up(db: Session, proposal: CheckoutProposal, reason_code: str, evidence: dict) -> StepUpRequest:
    step_up = StepUpRequest(proposal_id=proposal.id, binding_hash=proposal_binding(proposal), reason_code=reason_code, evidence=evidence)
    db.add(step_up)
    db.flush()
    write_audit(db, "STEP_UP_REQUESTED", "step_up", step_up.id, {"proposal_id": proposal.id, "binding_hash": step_up.binding_hash, "reason_code": reason_code})
    return step_up


def reject_step_up(db: Session, step_up_id: str) -> StepUpRequest:
    step_up = db.scalar(select(StepUpRequest).where(StepUpRequest.id == step_up_id).with_for_update())
    if step_up is None or step_up.status != "PENDING":
        raise AuthorizationDenied("Step-up is not pending")
    step_up.status = "REJECTED"
    step_up.resolved_at = datetime.now(timezone.utc)
    step_up.proposal.status = "BLOCKED"
    write_audit(db, "STEP_UP_REJECTED", "step_up", step_up.id, {"proposal_id": step_up.proposal_id, "razorpay_called": False})
    write_audit(db, "EXECUTION_BLOCKED", "proposal", step_up.proposal_id, {"reason_code": "STEP_UP_REJECTED", "razorpay_called": False})
    db.commit()
    return step_up


def approve_step_up(db: Session, step_up_id: str, razorpay: RazorpayPort) -> dict:
    step_up = db.scalar(select(StepUpRequest).where(StepUpRequest.id == step_up_id).with_for_update())
    if step_up is None or step_up.status != "PENDING":
        raise AuthorizationDenied("Step-up is not pending")
    if step_up.binding_hash != proposal_binding(step_up.proposal):
        raise AuthorizationDenied("Step-up binding does not match proposal")
    step_up.status = "APPROVED"
    step_up.resolved_at = datetime.now(timezone.utc)
    write_audit(db, "STEP_UP_APPROVED", "step_up", step_up.id, {"proposal_id": step_up.proposal_id, "scope": "APPROVE_ONCE", "binding_hash": step_up.binding_hash})
    db.commit()
    order = ExecutionService(db, razorpay).execute(step_up.proposal_id, approved_step_up=True)
    step_up = db.get(StepUpRequest, step_up.id)
    step_up.status = "CONSUMED"
    db.commit()
    return order

