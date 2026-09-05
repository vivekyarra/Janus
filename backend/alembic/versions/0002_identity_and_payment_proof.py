"""Bind human identity and verified Razorpay payments.

Revision ID: 0002_identity_payment
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa


revision = "0002_identity_payment"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("mandates") as batch:
        batch.add_column(sa.Column("created_by_subject", sa.String(80), nullable=True))
        batch.create_index("ix_mandates_created_by_subject", ["created_by_subject"])
    with op.batch_alter_table("checkout_proposals") as batch:
        batch.add_column(sa.Column("razorpay_payment_id", sa.String(100), nullable=True))
        batch.add_column(sa.Column("payment_status", sa.String(30), nullable=True))
        batch.add_column(sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_unique_constraint("uq_checkout_proposals_razorpay_payment_id", ["razorpay_payment_id"])


def downgrade() -> None:
    with op.batch_alter_table("checkout_proposals") as batch:
        batch.drop_constraint("uq_checkout_proposals_razorpay_payment_id", type_="unique")
        batch.drop_column("paid_at")
        batch.drop_column("payment_status")
        batch.drop_column("razorpay_payment_id")
    with op.batch_alter_table("mandates") as batch:
        batch.drop_index("ix_mandates_created_by_subject")
        batch.drop_column("created_by_subject")
