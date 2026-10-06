"""Seed data meets the minimums in BUILD_SPEC section 13."""

from sqlalchemy import func, select

from app.models import (
    Candidate,
    Client,
    Decision,
    DecisionStatus,
    FeedbackSignal,
    PreferenceMirrorSignal,
    RejectionFeedback,
)


def count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def test_seed_minimums(db):
    assert count(db, Client) >= 6
    assert count(db, Candidate) >= 12
    assert len(set(db.scalars(select(Decision.matchmaker_id)).all())) >= 3
    assert count(db, Decision) >= 30
    assert count(db, RejectionFeedback) >= 20
    assert count(db, FeedbackSignal) >= 20
    accepted = db.scalar(select(func.count()).select_from(Decision).where(Decision.status == DecisionStatus.accepted))
    assert accepted >= 5
    assert count(db, PreferenceMirrorSignal) >= 4  # mirror-capable patterns


def test_every_feedback_signal_is_internally_consistent(db):
    for s in db.scalars(select(FeedbackSignal)).all():
        stated = s.violation_type in ("dealbreaker", "stated_preference", "soft_preference")
        assert s.violated_stated_preference == stated
        assert s.evidence and s.explanation and s.category and s.attribute


def test_ananya_demo_persona(client, ids):
    detail = client.get(f"/api/clients/{ids['clients']['Ananya']}").json()
    prefs = {p["attribute"]: (p["preference_type"], p["value"]) for p in detail["preferences"]}
    assert prefs["intellectual_compatibility"][0] == "strong"
    assert prefs["children"] == ("strong", {"wants_children": True})
    assert prefs["smoking"] == ("dealbreaker", {"allowed": False})
    assert prefs["open_to_relocation"][1] == {"open": True}
    assert prefs["similar_lifestyle"][0] == "strong"
    assert detail["name"] == "Ananya"
