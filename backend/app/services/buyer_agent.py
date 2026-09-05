from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import AgentStep, AutonomousShopResponse, CandidateEvaluation
from app.db.models import CheckoutProposal, Mandate, Product
from app.domain.models import DecisionType, FinalDecision, HardCheck, HardGateResult, ReasonCode
from app.integrations.llm_adapter import SemanticModelPort
from app.integrations.razorpay_adapter import RazorpayPort
from app.services.audit_service import write_audit
from app.services.auth_service import Actor
from app.services.decision_engine import decide
from app.services.execution_service import ExecutionService
from app.services.hard_gate import evaluate_hard_constraints
from app.services.semantic_scorer import assess_semantic_constraints
from app.services.stepup_service import create_step_up


# Maps semantic outcome to a sortable rank: lower is better
_SEMANTIC_RANK = {"SUPPORTED": 0, "INSUFFICIENT_EVIDENCE": 1, "CONTRADICTED": 2}


def _worst_semantic_status(results: list[dict]) -> str:
    """Return the worst semantic status across all constraint results."""
    worst = "SUPPORTED"
    for r in results:
        status = r.get("status", "INSUFFICIENT_EVIDENCE")
        if _SEMANTIC_RANK.get(status, 1) > _SEMANTIC_RANK.get(worst, 0):
            worst = status
    return worst


class AutonomousBuyerAgent:
    """Six-stage autonomous shopping agent.

    Stage 1: Mandate ingestion — extract hard bounds and semantic constraints.
    Stage 2: Catalog scan — retrieve merchant products (strict isolation).
    Stage 3: Hard filtering — deterministic pre-filter against signed constraints.
    Stage 4: Semantic evaluation — LLM-based assessment of EVERY eligible candidate.
    Stage 5: Gateway dispatch — formal proposal through decision engine.
    Stage 6: Execution — atomic Razorpay order creation or step-up escalation.
    """

    def __init__(self, db: Session, semantic_model: SemanticModelPort, razorpay: RazorpayPort, actor: Actor) -> None:
        self.db = db
        self.semantic_model = semantic_model
        self.razorpay = razorpay
        self.actor = actor

    def run(self, mandate_id: str, merchant_id: str, auto_execute: bool = True) -> AutonomousShopResponse:
        steps: list[AgentStep] = []
        mandate = self.db.get(Mandate, mandate_id)
        if not mandate:
            raise HTTPException(404, detail={"reason_code": "MANDATE_NOT_FOUND"})
        if mandate.status != "ACTIVE":
            raise HTTPException(400, detail={"reason_code": "MANDATE_NOT_ACTIVE"})

        hard_bounds = mandate.hard_constraints
        max_amount_paise = hard_bounds.get("max_amount_paise", 0)
        allowed_currencies = set(hard_bounds.get("allowed_currencies", ["INR"]))
        allowed_categories = set(hard_bounds.get("allowed_categories", []))
        allowed_conditions = set(hard_bounds.get("allowed_conditions", ["new"]))

        # Stage 1: Contract extraction
        instruction = mandate.instruction_text or ""
        steps.append(
            AgentStep(
                step_num=1,
                title="Human Mandate Ingestion",
                detail=(
                    f"Parsed human delegation '{instruction[:60]}…'. "
                    f"Hard ceiling: ₹{max_amount_paise/100:,.2f} {list(allowed_currencies)[0]}. "
                    f"Authorized categories: {list(allowed_categories)}."
                ),
            )
        )

        # Stage 2: Catalog Scan — strict merchant isolation, no cross-tenant fallback
        query = select(Product).where(Product.active.is_(True), Product.merchant_id == merchant_id)
        products = list(self.db.scalars(query))

        if not products:
            steps.append(
                AgentStep(
                    step_num=2,
                    title="Catalog Scan Failed",
                    detail=f"No active products found for merchant '{merchant_id}'.",
                    status="FAILED",
                )
            )
            return AutonomousShopResponse(
                mandate_id=mandate.id,
                merchant_id=merchant_id,
                steps=steps,
                candidates_evaluated=[],
                selected_product_id=None,
                selected_product_name=None,
                agent_reasoning="No products available to shop.",
                proposal_id=None,
                decision="BLOCK",
                reason_code="CATALOG_EMPTY",
                razorpay_order_id=None,
                status="FAILED",
            )

        steps.append(
            AgentStep(
                step_num=2,
                title="Autonomous Catalog Scan",
                detail=f"Retrieved {len(products)} active SKUs from merchant '{merchant_id}'. Strict tenant isolation enforced.",
            )
        )

        # Stage 3: Deterministic hard-filter every SKU
        evaluations: list[CandidateEvaluation] = []
        eligible_candidates: list[Product] = []

        for prod in products:
            rejection = None
            if prod.price_paise > max_amount_paise:
                rejection = f"Exceeds budget (₹{prod.price_paise/100:,.2f} > ₹{max_amount_paise/100:,.2f})"
            elif prod.currency not in allowed_currencies:
                rejection = f"Currency {prod.currency} not allowed"
            elif allowed_categories and prod.category not in allowed_categories:
                rejection = f"Category '{prod.category}' not permitted"
            elif prod.condition not in allowed_conditions:
                rejection = f"Condition '{prod.condition}' not permitted"

            evaluations.append(
                CandidateEvaluation(
                    product_id=prod.id,
                    name=prod.name,
                    price_paise=prod.price_paise,
                    hard_eligible=rejection is None,
                    rejection_reason=rejection,
                    semantic_score=None,
                    semantic_notes="Pending semantic evaluation" if rejection is None else "Skipped (hard-ineligible)",
                )
            )

            if rejection is None:
                eligible_candidates.append(prod)

        steps.append(
            AgentStep(
                step_num=3,
                title="Deterministic Hard Filtering",
                detail=(
                    f"Evaluated {len(products)} SKUs against signed constraints: "
                    f"{len(eligible_candidates)} passed, "
                    f"{len(products) - len(eligible_candidates)} eliminated on monetary/category boundaries."
                ),
            )
        )

        # Stage 4: Semantic evaluation of EVERY eligible candidate using real LLM
        if not eligible_candidates:
            steps.append(
                AgentStep(
                    step_num=4,
                    title="Autonomous Boundary Protection",
                    detail="All merchant SKUs violate human spending limits. Agent halts safely.",
                    status="FAILED",
                )
            )
            return AutonomousShopResponse(
                mandate_id=mandate.id,
                merchant_id=merchant_id,
                steps=steps,
                candidates_evaluated=evaluations,
                selected_product_id=None,
                selected_product_name=None,
                agent_reasoning="No merchant product satisfies the human's hard constraints.",
                proposal_id=None,
                decision="BLOCK",
                reason_code="HARD_GATE_LIMIT_EXCEEDED",
                razorpay_order_id=None,
                status="BLOCKED",
            )

        semantic_constraints = mandate.semantic_constraints or []
        ranked: list[tuple[Product, str, str]] = []  # (product, worst_status, summary)

        for prod in eligible_candidates:
            if semantic_constraints:
                assessment = assess_semantic_constraints(
                    mandate.instruction_text, semantic_constraints, prod.attributes or {}, self.semantic_model
                )
                results_dicts = [r.model_dump(mode="json") for r in assessment.results]
                worst = _worst_semantic_status(results_dicts)
                reasons = [f"{r.constraint_id}: {r.status} ({r.reason[:80]})" for r in assessment.results]
                summary = "; ".join(reasons) if reasons else "No constraints evaluated"
            else:
                worst = "SUPPORTED"
                summary = "No semantic constraints — auto-supported"

            ranked.append((prod, worst, summary))

            # Update the evaluation entry with real semantic results
            for ev in evaluations:
                if ev.product_id == prod.id:
                    ev.semantic_score = round(1.0 - _SEMANTIC_RANK.get(worst, 1) * 0.5, 2)
                    ev.semantic_notes = summary
                    break

        # Sort: SUPPORTED first, then INSUFFICIENT_EVIDENCE, then CONTRADICTED.
        # Within same tier, prefer lower price (best value for human).
        ranked.sort(key=lambda item: (_SEMANTIC_RANK.get(item[1], 1), item[0].price_paise))
        best_product, best_status, best_summary = ranked[0]

        semantic_detail_lines = [
            f"  • {prod.name} ({prod.id}): {status} — {summary[:100]}"
            for prod, status, summary in ranked
        ]
        steps.append(
            AgentStep(
                step_num=4,
                title="LLM Semantic Evaluation (All Candidates)",
                detail=(
                    f"Ran real semantic assessment on {len(eligible_candidates)} eligible candidates:\n"
                    + "\n".join(semantic_detail_lines)
                    + f"\nBest match: '{best_product.name}' ({best_status})."
                ),
            )
        )

        reasoning = (
            f"Selected '{best_product.name}' (SKU: {best_product.id}) at ₹{best_product.price_paise/100:,.2f}. "
            f"Satisfies hard budget ceiling (₹{max_amount_paise/100:,.2f}). "
            f"Semantic outcome: {best_status}. {best_summary[:120]}."
        )

        # Stage 5: Proposal Construction & Gateway Dispatch
        agent_req_id = f"agent_autobuyer_{uuid.uuid4().hex[:12]}"
        proposal = CheckoutProposal(
            mandate_id=mandate.id,
            mandate_version=mandate.version,
            product_id=best_product.id,
            quantity=1,
            agent_request_id=agent_req_id,
            expected_amount_paise=best_product.price_paise,
            currency=best_product.currency,
        )
        self.db.add(proposal)
        self.db.flush()

        write_audit(
            self.db,
            "PROPOSAL_RECEIVED",
            "proposal",
            proposal.id,
            {
                "mandate_id": mandate.id,
                "mandate_version": mandate.version,
                "product_id": best_product.id,
                "quantity": 1,
                "agent_request_id": agent_req_id,
                "catalog_amount_paise": proposal.expected_amount_paise,
                "autonomous_agent": True,
                "actor_subject": self.actor.subject,
                "candidates_evaluated": len(products),
                "candidates_eligible": len(eligible_candidates),
            },
        )

        # Hard gate (formal re-evaluation for the selected product)
        hard = evaluate_hard_constraints(mandate, best_product, 1, agent_req_id, datetime.now(timezone.utc))
        if hard.status == "FAIL":
            proposal.status = "BLOCKED"
            decision = FinalDecision(decision=DecisionType.BLOCK, reason_code=hard.reason_code, hard_gate=hard, proposal_id=proposal.id)
            proposal.decision = decision.model_dump(mode="json")
            write_audit(self.db, "HARD_GATE_FAILED", "proposal", proposal.id, {"reason_code": hard.reason_code})
            write_audit(self.db, "FINAL_DECISION", "proposal", proposal.id, {"decision": "BLOCK", "reason_code": hard.reason_code})
            self.db.commit()
            steps.append(
                AgentStep(
                    step_num=5,
                    title="Gateway Boundary Rejection",
                    detail=f"Hard gate failed: {hard.reason_code.value}. Zero money transacted.",
                    status="FAILED",
                )
            )
            return AutonomousShopResponse(
                mandate_id=mandate.id,
                merchant_id=merchant_id,
                steps=steps,
                candidates_evaluated=evaluations,
                selected_product_id=best_product.id,
                selected_product_name=best_product.name,
                agent_reasoning=reasoning,
                proposal_id=proposal.id,
                decision="BLOCK",
                reason_code=hard.reason_code.value,
                razorpay_order_id=None,
                status="BLOCKED",
            )

        # Semantic assessment through formal gateway path
        semantic = assess_semantic_constraints(mandate.instruction_text, semantic_constraints, best_product.attributes or {}, self.semantic_model)
        write_audit(self.db, "SEMANTIC_ASSESSMENT_COMPLETED", "proposal", proposal.id, semantic.model_dump(mode="json"))

        decision = decide(hard, semantic)
        decision.proposal_id = proposal.id

        if decision.decision == DecisionType.ALLOW:
            proposal.status = "ALLOWED"
        else:
            proposal.status = "STEP_UP"
            step_up = create_step_up(self.db, proposal, decision.reason_code.value, semantic.model_dump(mode="json"))
            decision.step_up_id = step_up.id

        proposal.decision = decision.model_dump(mode="json")
        write_audit(self.db, "HARD_GATE_PASSED", "proposal", proposal.id, {"checks": hard.model_dump(mode="json")["checks"]})
        write_audit(self.db, "FINAL_DECISION", "proposal", proposal.id, {"decision": decision.decision, "reason_code": decision.reason_code, "razorpay_called": False})
        self.db.commit()

        steps.append(
            AgentStep(
                step_num=5,
                title="Gateway Authorization",
                detail=f"Hard gate PASSED. Semantic: {decision.decision.value} ({decision.reason_code.value}).",
            )
        )

        # Stage 6: Atomic Execution & Order Creation
        razorpay_order_id = None
        if decision.decision == DecisionType.ALLOW and auto_execute:
            order = ExecutionService(self.db, self.razorpay).execute(proposal.id)
            razorpay_order_id = order["id"]
            steps.append(
                AgentStep(
                    step_num=6,
                    title="Razorpay Order Created",
                    detail=f"Execution reservation secured. Razorpay test-mode order {razorpay_order_id} created for ₹{best_product.price_paise/100:,.2f}.",
                )
            )
        elif decision.decision == DecisionType.STEP_UP:
            steps.append(
                AgentStep(
                    step_num=6,
                    title="Human Oversight Escalation",
                    detail=f"Semantic ambiguity detected. Step-up dispatched (ID: {decision.step_up_id}).",
                )
            )
        else:
            steps.append(
                AgentStep(
                    step_num=6,
                    title="Autonomous Cycle Complete",
                    detail="Gateway blocked proposal. System failed closed safely.",
                )
            )

        return AutonomousShopResponse(
            mandate_id=mandate.id,
            merchant_id=merchant_id,
            steps=steps,
            candidates_evaluated=evaluations,
            selected_product_id=best_product.id,
            selected_product_name=best_product.name,
            agent_reasoning=reasoning,
            proposal_id=proposal.id,
            decision=decision.decision.value,
            reason_code=decision.reason_code.value if decision.reason_code else None,
            razorpay_order_id=razorpay_order_id,
            status=proposal.status,
            key_id=getattr(self.razorpay, "public_key_id", None) or getattr(self.razorpay, "key_id", None),
            amount_paise=best_product.price_paise,
            currency=best_product.currency,
            step_up_id=decision.step_up_id if hasattr(decision, "step_up_id") else None,
        )
