import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy import Uuid as SAUuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.preferences import PreferenceType
from app.db.base import Base, JSONType


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> uuid.UUID:
    return uuid.uuid4()


class PreferenceSource(StrEnum):
    onboarding = "onboarding"
    human_confirmed = "human_confirmed"


class DecisionStatus(StrEnum):
    shared = "shared"
    accepted = "accepted"
    rejected = "rejected"


class MirrorStatus(StrEnum):
    suggested = "suggested"
    confirmed = "confirmed"
    dismissed = "dismissed"


def _enum(py_enum: type[StrEnum], name: str) -> Enum:
    return Enum(py_enum, name=name)


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(SAUuid, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(Text)
    age: Mapped[int] = mapped_column(Integer)
    location: Mapped[str] = mapped_column(Text)
    profile_summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    preferences: Mapped[list["ClientPreference"]] = relationship(
        back_populates="client", cascade="all, delete-orphan"
    )


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[uuid.UUID] = mapped_column(SAUuid, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(Text)
    age: Mapped[int] = mapped_column(Integer)
    location: Mapped[str] = mapped_column(Text)
    # Nullable on purpose: a missing attribute is shown as "Unknown", never guessed.
    smokes: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    drinks: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    wants_children: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    willing_to_relocate: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    education: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Structured companions to the free-text education / career fields ("prestigious" | "standard").
    education_tier: Mapped[str | None] = mapped_column(String(20), nullable=True)
    career: Mapped[str | None] = mapped_column(Text, nullable=True)
    # "senior" | "mid" | "early"
    career_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    values_lifestyle: Mapped[dict] = mapped_column(JSONType, default=dict)
    bio: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ClientPreference(Base):
    __tablename__ = "client_preferences"
    __table_args__ = (Index("ix_client_preferences_client_id", "client_id"),)

    id: Mapped[uuid.UUID] = mapped_column(SAUuid, primary_key=True, default=new_id)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"))
    attribute: Mapped[str] = mapped_column(Text)
    value: Mapped[dict] = mapped_column(JSONType, default=dict)
    preference_type: Mapped[PreferenceType] = mapped_column(_enum(PreferenceType, "preference_type"))
    source: Mapped[PreferenceSource] = mapped_column(
        _enum(PreferenceSource, "preference_source"), default=PreferenceSource.onboarding
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    client: Mapped[Client] = relationship(back_populates="preferences")


class Decision(Base):
    """One row per client/candidate review or profile-share decision."""

    __tablename__ = "decisions"
    __table_args__ = (
        Index("ix_decisions_client_id", "client_id"),
        Index("ix_decisions_matchmaker_id", "matchmaker_id"),
        Index("ix_decisions_status", "status"),
        Index("ix_decisions_shared_at", "shared_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(SAUuid, primary_key=True, default=new_id)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"))
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"))
    matchmaker_id: Mapped[str] = mapped_column(String(20))
    status: Mapped[DecisionStatus] = mapped_column(_enum(DecisionStatus, "decision_status"))
    rejection_reason_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    shared_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    client: Mapped[Client] = relationship()
    candidate: Mapped[Candidate] = relationship()


class RejectionFeedback(Base):
    __tablename__ = "rejection_feedback"
    __table_args__ = (
        Index("ix_rejection_feedback_client_id", "client_id"),
        Index("ix_rejection_feedback_matchmaker_id", "matchmaker_id"),
        Index("ix_rejection_feedback_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(SAUuid, primary_key=True, default=new_id)
    # Nullable: a matchmaker may log a note before linking it to a specific shared profile.
    decision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("decisions.id", ondelete="SET NULL"), nullable=True
    )
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"))
    matchmaker_id: Mapped[str] = mapped_column(String(20))
    raw_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    signals: Mapped[list["FeedbackSignal"]] = relationship(
        back_populates="feedback", cascade="all, delete-orphan", order_by="FeedbackSignal.created_at"
    )


class FeedbackSignal(Base):
    __tablename__ = "feedback_signals"
    __table_args__ = (
        Index("ix_feedback_signals_feedback_id", "feedback_id"),
        Index("ix_feedback_signals_category", "category"),
        Index("ix_feedback_signals_observed_dimension", "observed_dimension"),
    )

    id: Mapped[uuid.UUID] = mapped_column(SAUuid, primary_key=True, default=new_id)
    feedback_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rejection_feedback.id", ondelete="CASCADE"))
    category: Mapped[str] = mapped_column(Text)
    # Finer behavioural tag (ObservedDimension); nullable so older rows derive it from category on read.
    observed_dimension: Mapped[str | None] = mapped_column(String(40), nullable=True)
    attribute: Mapped[str] = mapped_column(Text)
    violated_stated_preference: Mapped[bool] = mapped_column(Boolean)
    violation_type: Mapped[str] = mapped_column(Text)
    confidence: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text)
    evidence: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    feedback: Mapped[RejectionFeedback] = relationship(back_populates="signals")


class PreferenceMirrorSignal(Base):
    __tablename__ = "preference_mirror_signals"
    __table_args__ = (
        Index("ix_preference_mirror_signals_client_id", "client_id"),
        Index("ix_preference_mirror_signals_status", "status"),
        Index("ix_preference_mirror_signals_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(SAUuid, primary_key=True, default=new_id)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"))
    # Which hard-coded pattern rule produced this suggestion (see services/preference_mirror.py).
    rule_key: Mapped[str] = mapped_column(String(60))
    observed_attribute: Mapped[str] = mapped_column(Text)
    stated_attribute: Mapped[str] = mapped_column(Text)
    possible_pattern: Mapped[str] = mapped_column(Text)
    confidence: Mapped[str] = mapped_column(String(10))
    evidence_feedback_ids: Mapped[list] = mapped_column(JSONType, default=list)
    evidence_decision_ids: Mapped[list] = mapped_column(JSONType, default=list)
    status: Mapped[MirrorStatus] = mapped_column(
        _enum(MirrorStatus, "mirror_status"), default=MirrorStatus.suggested
    )
    human_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
