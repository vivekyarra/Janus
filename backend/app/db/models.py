from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class Product(Base):
    __tablename__ = "products"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(200))
    price_paise: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    category: Mapped[str] = mapped_column(String(80))
    condition: Mapped[str] = mapped_column(String(40), default="new")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)


class Mandate(Base):
    __tablename__ = "mandates"
    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=lambda: new_id("mnd"))
    instruction_text: Mapped[str] = mapped_column(Text)
    hard_constraints: Mapped[dict] = mapped_column(JSON)
    semantic_constraints: Mapped[list] = mapped_column(JSON, default=list)
    canonical_payload: Mapped[str] = mapped_column(Text)
    payload_hash: Mapped[str] = mapped_column(String(64))
    signature: Mapped[str] = mapped_column(Text)
    public_key: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    signed_version: Mapped[int] = mapped_column(Integer, default=1)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    max_executions: Mapped[int] = mapped_column(Integer, default=1)
    execution_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    proposals: Mapped[list["CheckoutProposal"]] = relationship(back_populates="mandate")


class CheckoutProposal(Base):
    __tablename__ = "checkout_proposals"
    __table_args__ = (UniqueConstraint("agent_request_id", name="uq_proposal_agent_request"),)
    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=lambda: new_id("prp"))
    mandate_id: Mapped[str] = mapped_column(ForeignKey("mandates.id"), index=True)
    mandate_version: Mapped[int] = mapped_column(Integer)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    agent_request_id: Mapped[str] = mapped_column(String(120), nullable=False)
    expected_amount_paise: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(20), default="RECEIVED")
    decision: Mapped[dict] = mapped_column(JSON, default=dict)
    razorpay_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    execution_error: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    mandate: Mapped[Mandate] = relationship(back_populates="proposals")
    step_up: Mapped["StepUpRequest | None"] = relationship(back_populates="proposal", uselist=False)


class StepUpRequest(Base):
    __tablename__ = "step_up_requests"
    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=lambda: new_id("sup"))
    proposal_id: Mapped[str] = mapped_column(ForeignKey("checkout_proposals.id"), unique=True)
    binding_hash: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    reason_code: Mapped[str] = mapped_column(String(80))
    evidence: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    proposal: Mapped[CheckoutProposal] = relationship(back_populates="step_up")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=lambda: new_id("evt"))
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    entity_id: Mapped[str] = mapped_column(String(80), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

