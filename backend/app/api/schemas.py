from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.domain.models import FinalDecision, HardConstraints, SemanticConstraint


class CreateMandateRequest(BaseModel):
    instruction_text: str = Field(min_length=3, max_length=1000)
    hard_constraints: HardConstraints
    semantic_constraints: list[SemanticConstraint] = Field(default_factory=list)
    expires_at: datetime


class CompileMandateRequest(BaseModel):
    instruction_text: str = Field(min_length=3, max_length=1000)
    merchant_id: str = Field(default="merchant_demo", min_length=3, max_length=80)


class ProposalRequest(BaseModel):
    mandate_id: str = Field(pattern=r"^mnd_[a-f0-9]+$")
    mandate_version: int = Field(ge=1)
    product_id: str = Field(pattern=r"^prod_[a-z0-9]+$")
    quantity: int = Field(ge=1, le=100)
    agent_request_id: str = Field(min_length=3, max_length=120, pattern=r"^[A-Za-z0-9._:-]+$")


class ProposalResponse(BaseModel):
    proposal_id: str
    status: str
    decision: FinalDecision


class ExecutionResponse(BaseModel):
    proposal_id: str
    razorpay_order_id: str
    status: str
    idempotent_replay: bool = False


class AuditRead(BaseModel):
    id: str
    event_type: str
    entity_type: str
    entity_id: str
    payload: dict[str, Any]
    created_at: datetime


class StepUpRead(BaseModel):
    id: str
    proposal_id: str
    status: str
    reason_code: str
    evidence: dict[str, Any]
    binding_hash: str
    created_at: datetime
    resolved_at: datetime | None
