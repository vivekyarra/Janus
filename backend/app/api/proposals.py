from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.schemas import (
    AutonomousShopRequest,
    AutonomousShopResponse,
    ExecutionResponse,
    PaymentVerificationRequest,
    PaymentVerificationResponse,
    ProposalRequest,
    ProposalResponse,
)
from app.api.dependencies import get_razorpay_adapter, get_semantic_model
from app.db.models import CheckoutProposal, Mandate, Product
from app.db.session import get_db
from app.domain.errors import JanusError
from app.domain.models import DecisionType, FinalDecision, HardCheck, HardGateResult, ReasonCode
from app.integrations.llm_adapter import SemanticModelPort
from app.integrations.razorpay_adapter import RazorpayPort
from app.services.audit_service import write_audit
from app.services.execution_service import ExecutionService
from app.services.hard_gate import evaluate_hard_constraints
from app.services.decision_engine import decide
from app.services.semantic_scorer import assess_semantic_constraints
from app.services.stepup_service import create_step_up
from app.services.auth_service import Actor, require_proposal_actor
from app.services.buyer_agent import AutonomousBuyerAgent
from app.services.payment_service import verify_checkout_payment
from app.config import get_settings


router = APIRouter(prefix="/api/v1/proposals", tags=["proposals"])


def _missing(reason: ReasonCode) -> HardGateResult:
    return HardGateResult(status="FAIL", reason_code=reason, checks=[HardCheck(name=reason.value.lower(), passed=False, expected="available", actual="missing", source="server_state" if reason == ReasonCode.MANDATE_NOT_FOUND else "merchant_catalog")])


@router.post("", response_model=ProposalResponse, status_code=201)
def create_proposal(request: ProposalRequest, db: Session = Depends(get_db), semantic_model: SemanticModelPort = Depends(get_semantic_model), actor: Actor = Depends(require_proposal_actor)):
    existing = db.scalar(select(CheckoutProposal).where(CheckoutProposal.agent_request_id == request.agent_request_id))
    if existing:
        write_audit(db, "DUPLICATE_REQUEST_REJECTED", "proposal", existing.id, {"agent_request_id": request.agent_request_id, "razorpay_order_id": existing.razorpay_order_id})
        db.commit()
        hard = _missing(ReasonCode.DUPLICATE_REQUEST)
        return ProposalResponse(proposal_id=existing.id, status=existing.status, decision=FinalDecision(decision=DecisionType.BLOCK, reason_code=ReasonCode.DUPLICATE_REQUEST, hard_gate=hard, proposal_id=existing.id, razorpay_called=bool(existing.razorpay_order_id)))

    mandate = db.get(Mandate, request.mandate_id)
    product = db.get(Product, request.product_id)
    if mandate is None:
        raise HTTPException(404, detail={"reason_code": ReasonCode.MANDATE_NOT_FOUND})
    if product is None:
        raise HTTPException(404, detail={"reason_code": ReasonCode.PRODUCT_NOT_FOUND})
    proposal = CheckoutProposal(mandate_id=mandate.id, mandate_version=request.mandate_version, product_id=product.id, quantity=request.quantity, agent_request_id=request.agent_request_id, expected_amount_paise=product.price_paise * request.quantity, currency=product.currency)
    db.add(proposal)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, detail={"reason_code": ReasonCode.DUPLICATE_REQUEST})
    write_audit(db, "PROPOSAL_RECEIVED", "proposal", proposal.id, {"mandate_id": mandate.id, "mandate_version": request.mandate_version, "product_id": product.id, "quantity": request.quantity, "agent_request_id": request.agent_request_id, "catalog_amount_paise": proposal.expected_amount_paise, "actor_subject": actor.subject, "actor_kind": actor.kind})

    if not product.active:
        hard = HardGateResult(status="FAIL", reason_code=ReasonCode.PRODUCT_INACTIVE, checks=[HardCheck(name="product_active", passed=False, expected=True, actual=False, source="merchant_catalog")])
    elif request.mandate_version != mandate.version:
        hard = HardGateResult(status="FAIL", reason_code=ReasonCode.MANDATE_VERSION_STALE, checks=[HardCheck(name="proposal_mandate_version_current", passed=False, expected=mandate.version, actual=request.mandate_version, source="request")])
    else:
        hard = evaluate_hard_constraints(mandate, product, request.quantity, request.agent_request_id, datetime.now(timezone.utc))
    if hard.status == "FAIL":
        proposal.status = "BLOCKED"
        decision = FinalDecision(decision=DecisionType.BLOCK, reason_code=hard.reason_code, hard_gate=hard, proposal_id=proposal.id)
        proposal.decision = decision.model_dump(mode="json")
        write_audit(db, "HARD_GATE_FAILED", "proposal", proposal.id, {"reason_code": hard.reason_code, "checks": hard.model_dump(mode="json")["checks"]})
        write_audit(db, "EXECUTION_BLOCKED", "proposal", proposal.id, {"reason_code": hard.reason_code, "razorpay_called": False})
    else:
        semantic = assess_semantic_constraints(mandate.instruction_text, mandate.semantic_constraints, product.attributes, semantic_model)
        write_audit(db, "SEMANTIC_ASSESSMENT_COMPLETED", "proposal", proposal.id, semantic.model_dump(mode="json"))
        decision = decide(hard, semantic)
        decision.proposal_id = proposal.id
        if decision.decision == DecisionType.ALLOW:
            proposal.status = "ALLOWED"
        else:
            proposal.status = "STEP_UP"
            step_up = create_step_up(db, proposal, decision.reason_code.value, semantic.model_dump(mode="json"))
            decision.step_up_id = step_up.id
        proposal.decision = decision.model_dump(mode="json")
        write_audit(db, "HARD_GATE_PASSED", "proposal", proposal.id, {"checks": hard.model_dump(mode="json")["checks"]})
    write_audit(db, "FINAL_DECISION", "proposal", proposal.id, {"decision": decision.decision, "reason_code": decision.reason_code, "razorpay_called": False})
    db.commit()
    return ProposalResponse(proposal_id=proposal.id, status=proposal.status, decision=decision)


@router.post("/{proposal_id}/execute", response_model=ExecutionResponse)
def execute_proposal(proposal_id: str, db: Session = Depends(get_db), razorpay: RazorpayPort = Depends(get_razorpay_adapter), _: Actor = Depends(require_proposal_actor)):
    try:
        order = ExecutionService(db, razorpay).execute(proposal_id)
    except JanusError as exc:
        raise HTTPException(exc.status_code, detail={"reason_code": exc.reason_code, "message": exc.message}) from exc
    return ExecutionResponse(proposal_id=proposal_id, razorpay_order_id=order["id"], status=order.get("status", "created"), idempotent_replay=order.get("idempotent_replay", False), key_id=order.get("key_id"), amount=order.get("amount"), currency=order.get("currency"), product_name=order.get("product_name"))


@router.post("/{proposal_id}/payments/verify", response_model=PaymentVerificationResponse)
def verify_payment(proposal_id: str, request: PaymentVerificationRequest, db: Session = Depends(get_db), razorpay: RazorpayPort = Depends(get_razorpay_adapter), _: Actor = Depends(require_proposal_actor)):
    try:
        return verify_checkout_payment(db, proposal_id, key_secret=get_settings().razorpay_key_secret, razorpay=razorpay, **request.model_dump())
    except JanusError as exc:
        raise HTTPException(exc.status_code, detail={"reason_code": exc.reason_code, "message": exc.message}) from exc


@router.post("/autonomous-shop", response_model=AutonomousShopResponse)
def autonomous_shop(
    request: AutonomousShopRequest,
    db: Session = Depends(get_db),
    semantic_model: SemanticModelPort = Depends(get_semantic_model),
    razorpay: RazorpayPort = Depends(get_razorpay_adapter),
    actor: Actor = Depends(require_proposal_actor),
):
    agent = AutonomousBuyerAgent(db, semantic_model, razorpay, actor)
    return agent.run(mandate_id=request.mandate_id, merchant_id=request.merchant_id, auto_execute=request.auto_execute)

