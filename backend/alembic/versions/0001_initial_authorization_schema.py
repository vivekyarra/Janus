"""Initial JANUS authorization schema.

Revision ID: 0001_initial
Revises:
"""
from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("products", sa.Column("id", sa.String(80), primary_key=True), sa.Column("merchant_id", sa.String(80), nullable=False), sa.Column("name", sa.String(200), nullable=False), sa.Column("price_paise", sa.Integer(), nullable=False), sa.Column("currency", sa.String(3), nullable=False), sa.Column("category", sa.String(80), nullable=False), sa.Column("condition", sa.String(40), nullable=False), sa.Column("active", sa.Boolean(), nullable=False), sa.Column("attributes", sa.JSON(), nullable=False))
    op.create_index("ix_products_merchant_id", "products", ["merchant_id"])
    op.create_table("mandates", sa.Column("id", sa.String(80), primary_key=True), sa.Column("instruction_text", sa.Text(), nullable=False), sa.Column("hard_constraints", sa.JSON(), nullable=False), sa.Column("semantic_constraints", sa.JSON(), nullable=False), sa.Column("canonical_payload", sa.Text(), nullable=False), sa.Column("payload_hash", sa.String(64), nullable=False), sa.Column("signature", sa.Text(), nullable=False), sa.Column("public_key", sa.Text(), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("version", sa.Integer(), nullable=False), sa.Column("signed_version", sa.Integer(), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("max_executions", sa.Integer(), nullable=False), sa.Column("execution_count", sa.Integer(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_mandates_status", "mandates", ["status"])
    op.create_table("checkout_proposals", sa.Column("id", sa.String(80), primary_key=True), sa.Column("mandate_id", sa.String(80), sa.ForeignKey("mandates.id"), nullable=False), sa.Column("mandate_version", sa.Integer(), nullable=False), sa.Column("product_id", sa.String(80), sa.ForeignKey("products.id"), nullable=False), sa.Column("quantity", sa.Integer(), nullable=False), sa.Column("agent_request_id", sa.String(120), nullable=False), sa.Column("expected_amount_paise", sa.Integer(), nullable=False), sa.Column("currency", sa.String(3), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("decision", sa.JSON(), nullable=False), sa.Column("razorpay_order_id", sa.String(100), nullable=True), sa.Column("execution_error", sa.String(200), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True), sa.UniqueConstraint("agent_request_id", name="uq_proposal_agent_request"), sa.UniqueConstraint("razorpay_order_id"))
    op.create_index("ix_checkout_proposals_mandate_id", "checkout_proposals", ["mandate_id"])
    op.create_index("ix_checkout_proposals_product_id", "checkout_proposals", ["product_id"])
    op.create_table("step_up_requests", sa.Column("id", sa.String(80), primary_key=True), sa.Column("proposal_id", sa.String(80), sa.ForeignKey("checkout_proposals.id"), nullable=False, unique=True), sa.Column("binding_hash", sa.String(64), nullable=False, unique=True), sa.Column("status", sa.String(20), nullable=False), sa.Column("reason_code", sa.String(80), nullable=False), sa.Column("evidence", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table("audit_events", sa.Column("id", sa.String(80), primary_key=True), sa.Column("event_type", sa.String(80), nullable=False), sa.Column("entity_type", sa.String(40), nullable=False), sa.Column("entity_id", sa.String(80), nullable=False), sa.Column("payload", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])
    op.create_index("ix_audit_events_entity_type", "audit_events", ["entity_type"])
    op.create_index("ix_audit_events_entity_id", "audit_events", ["entity_id"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("step_up_requests")
    op.drop_table("checkout_proposals")
    op.drop_table("mandates")
    op.drop_table("products")
