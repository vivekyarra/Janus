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

        # Idempotent replay: return existing result for already-completed proposals
        if proposal.status in {"ORDER_CREATED", "EXECUTED", "PAID"}:
            product = self.db.get(Product, proposal.product_id)
            replay_status = "paid" if proposal.status == "PAID" else "created"
            return {
                "id": proposal.razorpay_order_id,
                "status": replay_status,
                "idempotent_replay": True,
                "key_id": getattr(self.razorpay, "public_key_id", None),
                "amount": proposal.expected_amount_paise,
                "currency": proposal.currency,
                "product_name": product.name if product else None,
            }

        allowed_states = {"ALLOWED"} | ({"STEP_UP"} if approved_step_up else set())
        if proposal.status not in allowed_states:
            raise AuthorizationDenied(f"Proposal state {proposal.status} cannot execute")

        mandate = self.db.scalar(select(Mandate).where(Mandate.id == proposal.mandate_id).with_for_update())
        product = self.db.get(Product, proposal.product_id)
        if mandate is None or product is None:
            raise AuthorizationDenied("Authorization state unavailable")

        # Re-check hard constraints at execution time (revocation, expiry, etc.)
        result = evaluate_hard_constraints(mandate, product, proposal.quantity, proposal.agent_request_id, datetime.now(timezone.utc))
        if result.status == "FAIL":
            proposal.status = "BLOCKED"
            proposal.decision = {**proposal.decision, "execution_recheck": result.model_dump(mode="json")}
            write_audit(self.db, "EXECUTION_BLOCKED", "proposal", proposal.id, {"reason_code": result.reason_code, "hard_gate": result.model_dump(mode="json"), "razorpay_called": False})
            self.db.commit()
            raise AuthorizationDenied(str(result.reason_code))

        # Reserve execution slot and commit reservation to release DB row lock.
        # This prevents holding DB locks across external network calls and avoids deadlocks.
        # If Razorpay fails, we roll back the reservation explicitly.
        previous_execution_count = mandate.execution_count
        previous_mandate_status = mandate.status

        proposal.status = "EXECUTING"
        mandate.execution_count += 1
        if mandate.execution_count >= mandate.max_executions:
            mandate.status = "CONSUMED"
        write_audit(self.db, "EXECUTION_RESERVED", "proposal", proposal.id, {
            "mandate_id": mandate.id,
            "mandate_version": mandate.version,
            "execution_count": mandate.execution_count,
        })
        self.db.commit()

        try:
            order = self.razorpay.create_order(
                amount=proposal.expected_amount_paise,
                currency=proposal.currency,
                receipt=proposal.id,
                notes={"janus_proposal_id": proposal.id, "janus_mandate_id": mandate.id},
            )
        except RazorpayOrderCreationFailed as exc:
            # CRITICAL: Rollback the execution reservation on Razorpay failure.
            # The mandate slot must NOT be consumed by a failed external call.
            mandate = self.db.scalar(select(Mandate).where(Mandate.id == proposal.mandate_id).with_for_update())
            if mandate is not None:
                mandate.execution_count = previous_execution_count
                if mandate.status != "REVOKED":
                    mandate.status = previous_mandate_status
            proposal = self.db.scalar(select(CheckoutProposal).where(CheckoutProposal.id == proposal.id).with_for_update())
            if proposal is not None:
                proposal.status = "FAILED"
                proposal.execution_error = exc.reason_code
            write_audit(self.db, "EXECUTION_BLOCKED", "proposal", proposal.id, {
                "reason_code": exc.reason_code,
                "razorpay_called": True,
                "outcome": "failed_closed",
                "execution_count_rolled_back": True,
            })
            self.db.commit()
            raise

        # Razorpay succeeded — finalize
        proposal = self.db.scalar(select(CheckoutProposal).where(CheckoutProposal.id == proposal.id).with_for_update())
        proposal.status = "ORDER_CREATED"
        proposal.razorpay_order_id = order["id"]
        proposal.executed_at = datetime.now(timezone.utc)
        write_audit(self.db, "RAZORPAY_ORDER_CREATED", "proposal", proposal.id, {
            "razorpay_order_id": order["id"],
            "amount": proposal.expected_amount_paise,
            "currency": proposal.currency,
            "razorpay_called": True,
        })
        self.db.commit()
        return {
            **order,
            "key_id": getattr(self.razorpay, "public_key_id", None),
            "amount": proposal.expected_amount_paise,
            "currency": proposal.currency,
            "product_name": product.name,
        }
