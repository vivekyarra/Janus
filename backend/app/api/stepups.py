from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_razorpay_adapter
from app.api.schemas import ExecutionResponse, StepUpRead
from app.db.models import StepUpRequest
from app.db.session import get_db
from app.domain.errors import JanusError
from app.integrations.razorpay_adapter import RazorpayPort
from app.services.stepup_service import approve_step_up, reject_step_up
from app.services.auth_service import Actor, require_human_actor


router = APIRouter(prefix="/api/v1/step-ups", tags=["step-ups"])


@router.get("/{step_up_id}", response_model=StepUpRead)
def get_step_up(step_up_id: str, db: Session = Depends(get_db), _: Actor = Depends(require_human_actor)):
    value = db.get(StepUpRequest, step_up_id)
    if value is None:
        raise HTTPException(404, detail={"reason_code": "STEP_UP_NOT_FOUND"})
    return value


@router.post("/{step_up_id}/approve", response_model=ExecutionResponse)
def approve(step_up_id: str, db: Session = Depends(get_db), razorpay: RazorpayPort = Depends(get_razorpay_adapter), _: Actor = Depends(require_human_actor)):
    try:
        step_up = db.get(StepUpRequest, step_up_id)
        proposal_id = step_up.proposal_id if step_up else ""
        order = approve_step_up(db, step_up_id, razorpay)
        return ExecutionResponse(proposal_id=proposal_id, razorpay_order_id=order["id"], status=order.get("status", "created"), key_id=order.get("key_id"), amount=order.get("amount"), currency=order.get("currency"), product_name=order.get("product_name"))
    except JanusError as exc:
        raise HTTPException(exc.status_code, detail={"reason_code": exc.reason_code, "message": exc.message}) from exc


@router.post("/{step_up_id}/reject", response_model=StepUpRead)
def reject(step_up_id: str, db: Session = Depends(get_db), _: Actor = Depends(require_human_actor)):
    try:
        return reject_step_up(db, step_up_id)
    except JanusError as exc:
        raise HTTPException(exc.status_code, detail={"reason_code": exc.reason_code, "message": exc.message}) from exc
