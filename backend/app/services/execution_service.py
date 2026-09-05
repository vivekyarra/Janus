from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CheckoutProposal, Mandate, Product
from app.domain.errors import AuthorizationDenied, RazorpayOrderCreationFailed
from app.integrations.razorpay_adapter import RazorpayPort
from app.services.audit_service import write_audit
from app.services.hard_gate import evaluate_hard_constraints


class ExecutionService:
    def __init__(self, db: Session, razorpay: RazorpayPort) -> None:
        self.db = db
        self.razorpay = razorpay

    def execute(self, proposal_id: str, *, approved_step_up: bool = False) -> dict[str, Any]:
        proposal = self.db.scalar(select(CheckoutProposal).where(CheckoutProposal.id == proposal_id).with_for_update())
        if proposal is None:
            raise AuthorizationDenied("Proposal not found")
        if proposal.status in {"EXECUTED", "PAID"}:
            product = self.db.get(Product, proposal.product_id)
            return {"id": proposal.razorpay_order_id, "status": "created", "idempotent_replay": True, "key_id": getattr(self.razorpay, "public_key_id", None), "amount": proposal.expected_amount_paise, "currency": proposal.currency, "product_name": product.name if product else None}
        allowed_states = {"ALLOWED"} | ({"STEP_UP"} if approved_step_up else set())
        if proposal.status not in allowed_states:
            raise AuthorizationDenied(f"Proposal state {proposal.status} cannot execute")

        mandate = self.db.scalar(select(Mandate).where(Mandate.id == proposal.mandate_id).with_for_update())
        product = self.db.get(Product, proposal.product_id)
        if mandate is None or product is None:
            raise AuthorizationDenied("Authorization state unavailable")
        result = evaluate_hard_constraints(mandate, product, proposal.quantity, proposal.agent_request_id, datetime.now(timezone.utc))
        if result.status == "FAIL":
            proposal.status = "BLOCKED"
            proposal.decision = {**proposal.decision, "execution_recheck": result.model_dump(mode="json")}
            write_audit(self.db, "EXECUTION_BLOCKED", "proposal", proposal.id, {"reason_code": result.reason_code, "hard_gate": result.model_dump(mode="json"), "razorpay_called": False})
            self.db.commit()
            raise AuthorizationDenied(str(result.reason_code))

        proposal.status = "EXECUTING"
        mandate.execution_count += 1
        if mandate.execution_count >= mandate.max_executions:
            mandate.status = "CONSUMED"
        write_audit(self.db, "EXECUTION_RESERVED", "proposal", proposal.id, {"mandate_id": mandate.id, "mandate_version": mandate.version, "execution_count": mandate.execution_count})
        self.db.commit()

        try:
            order = self.razorpay.create_order(amount=proposal.expected_amount_paise, currency=proposal.currency, receipt=proposal.id, notes={"janus_proposal_id": proposal.id, "janus_mandate_id": mandate.id})
        except RazorpayOrderCreationFailed as exc:
            proposal = self.db.get(CheckoutProposal, proposal.id)
            proposal.status = "FAILED"
            proposal.execution_error = exc.reason_code
            write_audit(self.db, "EXECUTION_BLOCKED", "proposal", proposal.id, {"reason_code": exc.reason_code, "razorpay_called": True, "outcome": "failed_closed"})
            self.db.commit()
            raise

        proposal = self.db.get(CheckoutProposal, proposal.id)
        proposal.status = "EXECUTED"
        proposal.razorpay_order_id = order["id"]
        proposal.executed_at = datetime.now(timezone.utc)
        write_audit(self.db, "RAZORPAY_ORDER_CREATED", "proposal", proposal.id, {"razorpay_order_id": order["id"], "amount": proposal.expected_amount_paise, "currency": proposal.currency, "razorpay_called": True})
        self.db.commit()
        return {**order, "key_id": getattr(self.razorpay, "public_key_id", None), "amount": proposal.expected_amount_paise, "currency": proposal.currency, "product_name": product.name}
