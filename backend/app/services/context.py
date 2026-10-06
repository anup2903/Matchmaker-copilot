"""Load ORM rows into the plain dataclasses the pure services work with."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.preferences import FeedbackCategory, infer_dimension
from app.models import Candidate, Client, ClientPreference, Decision, DecisionStatus, RejectionFeedback
from app.services.domain import (
    AcceptedIn,
    CandidateIn,
    ClientIn,
    FeedbackIn,
    PreferenceIn,
    SignalIn,
)


def client_in(client: Client) -> ClientIn:
    return ClientIn(id=str(client.id), name=client.name, location=client.location)


def preference_in(p: ClientPreference) -> PreferenceIn:
    return PreferenceIn(
        attribute=p.attribute, value=dict(p.value or {}), type=str(p.preference_type), source=str(p.source)
    )


def candidate_in(c: Candidate) -> CandidateIn:
    return CandidateIn(
        id=str(c.id),
        name=c.name,
        age=c.age,
        location=c.location,
        smokes=c.smokes,
        drinks=c.drinks,
        wants_children=c.wants_children,
        willing_to_relocate=c.willing_to_relocate,
        education=c.education,
        education_tier=c.education_tier,
        career=c.career,
        career_level=c.career_level,
        values_lifestyle=dict(c.values_lifestyle or {}),
    )


def load_preferences(db: Session, client_id: uuid.UUID) -> list[PreferenceIn]:
    rows = db.scalars(
        select(ClientPreference).where(ClientPreference.client_id == client_id).order_by(ClientPreference.created_at)
    ).all()
    return [preference_in(p) for p in rows]


def load_feedback(db: Session, client_id: uuid.UUID) -> list[FeedbackIn]:
    """All saved (human-confirmed) rejection notes for a client, newest first."""
    rows = db.scalars(
        select(RejectionFeedback)
        .where(RejectionFeedback.client_id == client_id)
        .options(selectinload(RejectionFeedback.signals))
        .order_by(RejectionFeedback.created_at.desc())
    ).all()
    return [
        FeedbackIn(
            id=str(fb.id),
            created_at=fb.created_at,
            decision_id=str(fb.decision_id) if fb.decision_id else None,
            signals=tuple(
                SignalIn(
                    feedback_id=str(fb.id),
                    category=s.category,
                    attribute=s.attribute,
                    evidence=s.evidence,
                    violation_type=s.violation_type,
                    confidence=s.confidence,
                    created_at=fb.created_at,
                    observed_dimension=s.observed_dimension
                    or infer_dimension(FeedbackCategory(s.category), s.attribute, s.evidence).value,
                    decision_id=str(fb.decision_id) if fb.decision_id else None,
                )
                for s in fb.signals
            ),
        )
        for fb in rows
    ]


def flatten_signals(feedback: list[FeedbackIn]) -> list[SignalIn]:
    return [s for fb in feedback for s in fb.signals]


def load_accepted(db: Session, client_id: uuid.UUID) -> list[AcceptedIn]:
    rows = db.scalars(
        select(Decision)
        .where(Decision.client_id == client_id, Decision.status == DecisionStatus.accepted)
        .options(selectinload(Decision.candidate))
        .order_by(Decision.shared_at.desc())
    ).all()
    return [
        AcceptedIn(decision_id=str(d.id), candidate=candidate_in(d.candidate), decided_at=d.shared_at) for d in rows
    ]
