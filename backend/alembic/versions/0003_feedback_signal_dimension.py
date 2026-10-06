"""add observed_dimension to feedback_signals

Revision ID: 0003
Revises: 0002
Create Date: 2026-01-03
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("feedback_signals", sa.Column("observed_dimension", sa.String(40), nullable=True))
    op.create_index("ix_feedback_signals_observed_dimension", "feedback_signals", ["observed_dimension"])


def downgrade() -> None:
    op.drop_index("ix_feedback_signals_observed_dimension", table_name="feedback_signals")
    op.drop_column("feedback_signals", "observed_dimension")
