from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class MandateStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    CONSUMED = "CONSUMED"


class ProposalStatus(StrEnum):
    RECEIVED = "RECEIVED"
    BLOCKED = "BLOCKED"
    STEP_UP = "STEP_UP"
    ALLOWED = "ALLOWED"
    EXECUTING = "EXECUTING"
    ORDER_CREATED = "ORDER_CREATED"
    EXECUTED = "EXECUTED"  # legacy alias for ORDER_CREATED
    PAID = "PAID"
    FAILED = "FAILED"


class StepUpStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CONSUMED = "CONSUMED"


class DecisionType(StrEnum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    STEP_UP = "STEP_UP"


class ReasonCode(StrEnum):
    MANDATE_NOT_FOUND = "MANDATE_NOT_FOUND"
    SIGNATURE_INVALID = "SIGNATURE_INVALID"
    MANDATE_REVOKED = "MANDATE_REVOKED"
    MANDATE_EXPIRED = "MANDATE_EXPIRED"
    MANDATE_CONSUMED = "MANDATE_CONSUMED"
    MANDATE_VERSION_STALE = "MANDATE_VERSION_STALE"
    MERCHANT_NOT_ALLOWED = "MERCHANT_NOT_ALLOWED"
    CURRENCY_NOT_ALLOWED = "CURRENCY_NOT_ALLOWED"
    CATEGORY_NOT_ALLOWED = "CATEGORY_NOT_ALLOWED"
    CONDITION_NOT_ALLOWED = "CONDITION_NOT_ALLOWED"
    QUANTITY_EXCEEDED = "QUANTITY_EXCEEDED"
    AMOUNT_LIMIT_EXCEEDED = "AMOUNT_LIMIT_EXCEEDED"
    EXECUTION_LIMIT_EXCEEDED = "EXECUTION_LIMIT_EXCEEDED"
    DUPLICATE_REQUEST = "DUPLICATE_REQUEST"
    PRODUCT_NOT_FOUND = "PRODUCT_NOT_FOUND"
    PRODUCT_INACTIVE = "PRODUCT_INACTIVE"
    SEMANTIC_SUPPORTED = "SEMANTIC_SUPPORTED"
    SEMANTIC_CONTRADICTED = "SEMANTIC_CONTRADICTED"
    SEMANTIC_INSUFFICIENT_EVIDENCE = "SEMANTIC_INSUFFICIENT_EVIDENCE"
    SEMANTIC_SERVICE_UNAVAILABLE = "SEMANTIC_SERVICE_UNAVAILABLE"
    RAZORPAY_ORDER_CREATION_FAILED = "RAZORPAY_ORDER_CREATION_FAILED"


class HardConstraints(BaseModel):
    max_amount_paise: int = Field(gt=0)
    allowed_currencies: list[str] = Field(min_length=1)
    allowed_merchants: list[str] = Field(min_length=1)
    allowed_categories: list[str] = Field(min_length=1)
    allowed_conditions: list[str] = Field(default_factory=lambda: ["new"])
    max_quantity: int = Field(default=1, ge=1)
    max_executions: int = Field(default=1, ge=1)


class SemanticConstraint(BaseModel):
    id: str
    text: str = Field(min_length=1, max_length=300)


class CatalogProductInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]+$")
    merchant_id: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]+$")
    name: str = Field(min_length=2, max_length=200)
    price_paise: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    category: str = Field(min_length=2, max_length=80)
    condition: str = Field(default="new", min_length=2, max_length=40)
    active: bool = True
    attributes: dict[str, Any] = Field(default_factory=dict)


class UnresolvedField(BaseModel):
    field: str
    reason: str


class MandateDraft(BaseModel):
    instruction_text: str
    hard_constraints: HardConstraints | None = None
    semantic_constraints: list[SemanticConstraint] = Field(default_factory=list)
    unresolved: list[UnresolvedField] = Field(default_factory=list)


class MandateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    instruction_text: str
    hard_constraints: dict[str, Any]
    semantic_constraints: list[dict[str, Any]]
    status: MandateStatus
    version: int
    expires_at: datetime
    max_executions: int
    execution_count: int
    signature: str
    public_key: str
    created_at: datetime
    revoked_at: datetime | None
    created_by_subject: str | None


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    merchant_id: str
    name: str
    price_paise: int
    currency: str
    category: str
    condition: str
    active: bool
    attributes: dict[str, Any]


class HardCheck(BaseModel):
    name: str
    passed: bool
    expected: Any = None
    actual: Any = None
    source: Literal["signed_mandate", "merchant_catalog", "server_state", "request"]


class HardGateResult(BaseModel):
    status: Literal["PASS", "FAIL"]
    reason_code: ReasonCode | None = None
    checks: list[HardCheck]


class EvidenceItem(BaseModel):
    field: str
    value: Any
    source: Literal["merchant_catalog"] = "merchant_catalog"


class SemanticConstraintResult(BaseModel):
    constraint_id: str
    status: Literal["SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"]
    evidence: list[EvidenceItem]
    reason: str


class SemanticAssessment(BaseModel):
    results: list[SemanticConstraintResult]
    service_status: Literal["OK", "UNAVAILABLE"] = "OK"


class FinalDecision(BaseModel):
    decision: DecisionType
    reason_code: ReasonCode | None = None
    hard_gate: HardGateResult
    semantic: SemanticAssessment | None = None
    proposal_id: str | None = None
    step_up_id: str | None = None
    razorpay_called: bool = False
