"""drop dashboard_snapshots (dashboard removed from the product)

Revision ID: 0002
Revises: 0001
Create Date: 2026-01-02
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("dashboard_snapshots")


def downgrade() -> None:
    op.create_table(
        "dashboard_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("period_label", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
