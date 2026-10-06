"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-01-01
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

JSONB = postgresql.JSONB(astext_type=sa.Text())
TS = sa.DateTime(timezone=True)


def _uuid_pk() -> sa.Column:
    return sa.Column("id", sa.Uuid(), primary_key=True)


def upgrade() -> None:
    op.create_table(
        "clients",
        _uuid_pk(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("age", sa.Integer(), nullable=False),
        sa.Column("location", sa.Text(), nullable=False),
        sa.Column("profile_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "candidates",
        _uuid_pk(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("age", sa.Integer(), nullable=False),
        sa.Column("location", sa.Text(), nullable=False),
        sa.Column("smokes", sa.Boolean(), nullable=True),
        sa.Column("drinks", sa.Boolean(), nullable=True),
        sa.Column("wants_children", sa.Boolean(), nullable=True),
        sa.Column("willing_to_relocate", sa.Boolean(), nullable=True),
        sa.Column("education", sa.Text(), nullable=True),
        sa.Column("education_tier", sa.String(20), nullable=True),
        sa.Column("career", sa.Text(), nullable=True),
        sa.Column("career_level", sa.String(20), nullable=True),
        sa.Column("values_lifestyle", JSONB, nullable=False, server_default="{}"),
        sa.Column("bio", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "client_preferences",
        _uuid_pk(),
        sa.Column("client_id", sa.Uuid(), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attribute", sa.Text(), nullable=False),
        sa.Column("value", JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "preference_type",
            sa.Enum("dealbreaker", "strong", "soft", name="preference_type"),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.Enum("onboarding", "human_confirmed", name="preference_source"),
            nullable=False,
            server_default="onboarding",
        ),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_client_preferences_client_id", "client_preferences", ["client_id"])

    op.create_table(
        "decisions",
        _uuid_pk(),
        sa.Column("client_id", sa.Uuid(), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "candidate_id", sa.Uuid(), sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("matchmaker_id", sa.String(20), nullable=False),
        sa.Column(
            "status",
            sa.Enum("shared", "accepted", "rejected", name="decision_status"),
            nullable=False,
        ),
        sa.Column("rejection_reason_category", sa.Text(), nullable=True),
        sa.Column("shared_at", TS, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_decisions_client_id", "decisions", ["client_id"])
    op.create_index("ix_decisions_matchmaker_id", "decisions", ["matchmaker_id"])
    op.create_index("ix_decisions_status", "decisions", ["status"])
    op.create_index("ix_decisions_shared_at", "decisions", ["shared_at"])

    op.create_table(
        "rejection_feedback",
        _uuid_pk(),
        sa.Column("decision_id", sa.Uuid(), sa.ForeignKey("decisions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("client_id", sa.Uuid(), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("matchmaker_id", sa.String(20), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_rejection_feedback_client_id", "rejection_feedback", ["client_id"])
    op.create_index("ix_rejection_feedback_matchmaker_id", "rejection_feedback", ["matchmaker_id"])
    op.create_index("ix_rejection_feedback_created_at", "rejection_feedback", ["created_at"])

    op.create_table(
        "feedback_signals",
        _uuid_pk(),
        sa.Column(
            "feedback_id",
            sa.Uuid(),
            sa.ForeignKey("rejection_feedback.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("attribute", sa.Text(), nullable=False),
        sa.Column("violated_stated_preference", sa.Boolean(), nullable=False),
        sa.Column("violation_type", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_feedback_signals_feedback_id", "feedback_signals", ["feedback_id"])
    op.create_index("ix_feedback_signals_category", "feedback_signals", ["category"])

    op.create_table(
        "preference_mirror_signals",
        _uuid_pk(),
        sa.Column("client_id", sa.Uuid(), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_key", sa.String(60), nullable=False),
        sa.Column("observed_attribute", sa.Text(), nullable=False),
        sa.Column("stated_attribute", sa.Text(), nullable=False),
        sa.Column("possible_pattern", sa.Text(), nullable=False),
        sa.Column("confidence", sa.String(10), nullable=False),
        sa.Column("evidence_feedback_ids", JSONB, nullable=False, server_default="[]"),
        sa.Column("evidence_decision_ids", JSONB, nullable=False, server_default="[]"),
        sa.Column(
            "status",
            sa.Enum("suggested", "confirmed", "dismissed", name="mirror_status"),
            nullable=False,
            server_default="suggested",
        ),
        sa.Column("human_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("confirmed_at", TS, nullable=True),
        sa.Column("dismissed_at", TS, nullable=True),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TS, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_preference_mirror_signals_client_id", "preference_mirror_signals", ["client_id"])
    op.create_index("ix_preference_mirror_signals_status", "preference_mirror_signals", ["status"])
    op.create_index("ix_preference_mirror_signals_created_at", "preference_mirror_signals", ["created_at"])

    op.create_table(
        "dashboard_snapshots",
        _uuid_pk(),
        sa.Column("period_label", sa.Text(), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    for table in (
        "dashboard_snapshots",
        "preference_mirror_signals",
        "feedback_signals",
        "rejection_feedback",
        "decisions",
        "client_preferences",
        "candidates",
        "clients",
    ):
        op.drop_table(table)
    for enum_name in ("mirror_status", "decision_status", "preference_source", "preference_type"):
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
