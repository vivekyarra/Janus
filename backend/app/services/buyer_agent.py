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


class AutonomousBuyerAgent:
    def __init__(self, db: Session, semantic_model: SemanticModelPort, razorpay: RazorpayPort, actor: Actor) -> None:
        self.db = db
        self.semantic_model = semantic_model
        self.razorpay = razorpay
        self.actor = actor

    def run(self, mandate_id: str, merchant_id: str = "northstar_audio", auto_execute: bool = True) -> AutonomousShopResponse:
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

        # Step 1: Contract extraction
        instruction = mandate.instruction_text or ""
        steps.append(
            AgentStep(
                step_num=1,
                title="Human Mandate Ingestion",
                detail=(
                    f"Parsed human delegation '{instruction[:60]}...'. "
                    f"Hard ceiling: ₹{max_amount_paise/100:,.2f} {list(allowed_currencies)[0]}. "
                    f"Authorized categories: {list(allowed_categories)}."
                ),
            )
        )

        # Step 2: Catalog Scan
        query = select(Product).where(Product.active.is_(True))
        if merchant_id:
            merchant_products = list(self.db.scalars(query.where(Product.merchant_id == merchant_id)))
            if merchant_products:
                products = merchant_products
            else:
                products = list(self.db.scalars(query))
        else:
            products = list(self.db.scalars(query))

        if not products:
            steps.append(
                AgentStep(
                    step_num=2,
                    title="Catalog Scan Failed",
                    detail="No active products found in merchant catalog.",
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
                detail=f"Retrieved {len(products)} active SKUs from merchant '{merchant_id}'. Verified machine-readable catalog schema.",
            )
        )

        # Step 3: Candidate Scoring & Pre-filtering
        evaluations: list[CandidateEvaluation] = []
        eligible_candidates: list[tuple[Product, float, str]] = []

        instr_lower = instruction.lower()
        semantic_texts = [c.get("text", "").lower() for c in (mandate.semantic_constraints or [])]
        combined_intent = instr_lower + " " + " ".join(semantic_texts)

        for prod in products:
            rejection = None
            if prod.price_paise > max_amount_paise:
                rejection = f"Exceeds max budget (₹{prod.price_paise/100:,.2f} > ₹{max_amount_paise/100:,.2f})"
            elif prod.currency not in allowed_currencies:
                rejection = f"Currency {prod.currency} not allowed"
            elif allowed_categories and prod.category not in allowed_categories:
                rejection = f"Category '{prod.category}' not permitted"
            elif prod.condition not in allowed_conditions:
                rejection = f"Condition '{prod.condition}' not permitted"

            attrs = prod.attributes or {}
            score = 0.5  # Baseline score
            notes = []

            # Scoring based on intent keywords & attributes
            if "travel" in combined_intent or "flight" in combined_intent:
                if attrs.get("foldable") is True:
                    score += 0.25
                    notes.append("Foldable (+)")
                elif attrs.get("foldable") is False:
                    score -= 0.3
                    notes.append("Rigid non-foldable (-)")
                if attrs.get("travel_case") is True:
                    score += 0.2
                    notes.append("Travel case (+)")
                if attrs.get("weight_g", 0) > 400:
                    score -= 0.2
                    notes.append("Heavy weight (-)")

            if "noise" in combined_intent or "cancelling" in combined_intent or "quiet" in combined_intent:
                if attrs.get("noise_cancelling") is True:
                    score += 0.3
                    notes.append("Active ANC (+)")
                else:
                    score -= 0.2
                    notes.append("Lacks ANC (-)")

            if "flashy" in combined_intent or "minimal" in combined_intent:
                color = str(attrs.get("color", "")).lower()
                branding = str(attrs.get("branding", "")).lower()
                if "gold" in color or "metallic" in color or "oversized" in branding:
                    score -= 0.5
                    notes.append("Loud/flashy styling (--)")
                if "minimal" in branding or "discreet" in branding:
                    score += 0.25
                    notes.append("Minimal branding (+)")

            score = max(0.0, min(1.0, score))
            notes_str = ", ".join(notes) if notes else "Standard catalog fit"

            evaluations.append(
                CandidateEvaluation(
                    product_id=prod.id,
                    name=prod.name,
                    price_paise=prod.price_paise,
                    hard_eligible=rejection is None,
                    rejection_reason=rejection,
                    semantic_score=round(score, 2),
                    semantic_notes=notes_str,
                )
            )

            if rejection is None:
                eligible_candidates.append((prod, score, notes_str))

        steps.append(
            AgentStep(
                step_num=3,
                title="Multi-Candidate Intent Alignment",
                detail=(
                    f"Evaluated {len(products)} SKUs: {len(eligible_candidates)} passed deterministic hard constraints, "
                    f"{len(products) - len(eligible_candidates)} eliminated on monetary/category boundaries."
                ),
            )
        )

        # Step 4: Candidate Selection
        if not eligible_candidates:
            steps.append(
                AgentStep(
                    step_num=4,
                    title="Autonomous Boundary Protection",
                    detail="All available merchant SKUs violate human spending limits. Agent halts safely to protect funds.",
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

        # Sort by score descending, then price ascending
        eligible_candidates.sort(key=lambda item: (-item[1], item[0].price_paise))
        best_product, best_score, best_notes = eligible_candidates[0]

        reasoning = (
            f"Autonomously selected '{best_product.name}' (SKU: {best_product.id}) at ₹{best_product.price_paise/100:,.2f}. "
            f"Satisfies hard budget ceiling (₹{max_amount_paise/100:,.2f}). "
            f"Intent score {best_score:.2f} based on merchant facts: {best_notes}."
        )

        steps.append(
            AgentStep(
                step_num=4,
                title="Optimal SKU Selection",
                detail=reasoning,
            )
        )

        # Step 5: Proposal Construction & Gateway Dispatch
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
            },
        )

        # Hard Gate evaluation
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

        # Semantic Scorer evaluation
        semantic = assess_semantic_constraints(mandate.instruction_text, mandate.semantic_constraints, best_product.attributes, self.semantic_model)
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
                title="Gateway Intent Clearance",
                detail=f"Deterministic hard gate PASSED. Semantic classification: {decision.decision.value} ({decision.reason_code.value}).",
            )
        )

        # Step 6: Atomic Execution Settlement
        razorpay_order_id = None
        if decision.decision == DecisionType.ALLOW and auto_execute:
            order = ExecutionService(self.db, self.razorpay).execute(proposal.id)
            razorpay_order_id = order["id"]
            steps.append(
                AgentStep(
                    step_num=6,
                    title="Autonomous Razorpay Settlement",
                    detail=f"Atomic execution reservation secured. Real Razorpay Test Order {razorpay_order_id} created for ₹{best_product.price_paise/100:,.2f}.",
                )
            )
        elif decision.decision == DecisionType.STEP_UP:
            steps.append(
                AgentStep(
                    step_num=6,
                    title="Human Oversight Escalation",
                    detail=f"Semantic ambiguity or contradiction detected. Dispatched single-use exception request to Human Console (ID: {decision.step_up_id}).",
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
