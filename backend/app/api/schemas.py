from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models import CatalogProductInput, FinalDecision, HardConstraints, SemanticConstraint


class CreateMandateRequest(BaseModel):
    instruction_text: str = Field(min_length=3, max_length=1000)
    hard_constraints: HardConstraints
    semantic_constraints: list[SemanticConstraint] = Field(default_factory=list)
    expires_at: datetime


class CompileMandateRequest(BaseModel):
    instruction_text: str = Field(min_length=3, max_length=1000)
    merchant_id: str = Field(default="merchant_demo", min_length=3, max_length=80)


class ProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mandate_id: str = Field(pattern=r"^mnd_[a-f0-9]+$")
    mandate_version: int = Field(ge=1)
    product_id: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]+$")
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
    key_id: str | None = None
    amount: int | None = None
    currency: str | None = None
    product_name: str | None = None


class PaymentVerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    razorpay_payment_id: str = Field(pattern=r"^pay_[A-Za-z0-9]+$", max_length=100)
    razorpay_order_id: str = Field(pattern=r"^order_[A-Za-z0-9]+$", max_length=100)
    razorpay_signature: str = Field(pattern=r"^[a-f0-9]{64}$")


class PaymentVerificationResponse(BaseModel):
    proposal_id: str
    razorpay_order_id: str
    razorpay_payment_id: str
    status: str
    idempotent_replay: bool = False


class CatalogImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    merchant_id: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]+$")
    products: list[CatalogProductInput] = Field(min_length=1, max_length=5000)


class CatalogImportResponse(BaseModel):
    merchant_id: str
    created: int
    updated: int
    unchanged: int
    total: int


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


class CandidateEvaluation(BaseModel):
    product_id: str
    name: str
    price_paise: int
    hard_eligible: bool
    rejection_reason: str | None = None
    semantic_score: float = 0.0
    semantic_notes: str | None = None


class AgentStep(BaseModel):
    step_num: int
    title: str
    detail: str
    status: str = "COMPLETED"


class AutonomousShopRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mandate_id: str = Field(pattern=r"^mnd_[a-f0-9]+$")
    merchant_id: str = Field(default="northstar_audio", min_length=3, max_length=80)
    auto_execute: bool = True


class AutonomousShopResponse(BaseModel):
    mandate_id: str
    merchant_id: str
    steps: list[AgentStep]
    candidates_evaluated: list[CandidateEvaluation]
    selected_product_id: str | None
    selected_product_name: str | None
    agent_reasoning: str
    proposal_id: str | None
    decision: str
    reason_code: str | None
    razorpay_order_id: str | None
    status: str
    key_id: str | None = None
    amount_paise: int | None = None
    currency: str = "INR"
    step_up_id: str | None = None


class MerchantMetricsResponse(BaseModel):
    merchant_id: str
    catalog_sku_count: int
    machine_readability_score: float
    total_proposals: int
    allowed_count: int
    stepup_count: int
    blocked_count: int
    conversion_rate_pct: float
    autonomous_gmv_paise: int
    blocked_overspend_paise: int
    p95_authorization_latency_ms: float

