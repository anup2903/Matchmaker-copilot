"""Seed (or reset) the Matchmaker Copilot database with realistic mock data.

    python seed/seed.py              # add data (fails on duplicates if already seeded)
    python seed/seed.py --reset      # wipe all tables, then seed
    python seed/seed.py --if-empty   # seed only when there are no clients yet (used by docker compose)

IDs are deterministic (uuid5 of a slug) so demo links and tests are stable across resets.
All data is invented for the assessment. Nothing here is real The Date Crew data.
"""

import argparse
import json
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"

try:  # inside the backend container the app package is already importable
    import app  # noqa: F401
except ImportError:  # local run: seed/ sits next to backend/
    sys.path.insert(0, str(HERE.parent / "backend"))

from sqlalchemy import delete, func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.preferences import (  # noqa: E402
    VIOLATION_TYPES_STATED,
    FeedbackCategory,
    PreferenceType,
    ViolationType,
    classify_violation,
)
from app.models import (  # noqa: E402
    Candidate,
    Client,
    ClientPreference,
    Decision,
    DecisionStatus,
    FeedbackSignal,
    PreferenceMirrorSignal,
    PreferenceSource,
    RejectionFeedback,
)
from app.schemas.feedback import StructuredSignal  # noqa: E402
from app.services import mirror_store  # noqa: E402
from app.services.domain import PreferenceIn  # noqa: E402
from app.services.llm.signal_rules import explain  # noqa: E402

NAMESPACE = uuid.UUID("6f1d3b1e-7a4c-4c1e-9a55-0d3c2b7a9f10")


def _id(kind: str, slug: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, f"{kind}:{slug}")


def _load(name: str):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def reset_tables(session: Session) -> None:
    for model in (
        FeedbackSignal,
        RejectionFeedback,
        PreferenceMirrorSignal,
        Decision,
        ClientPreference,
            Candidate,
        Client,
    ):
        session.execute(delete(model))
    session.commit()


def seed_database(session: Session, reset: bool = False, if_empty: bool = False) -> dict[str, int]:
    if reset:
        reset_tables(session)
    elif if_empty and session.scalar(select(func.count()).select_from(Client)):
        return {"skipped": 1}

    now = datetime.now(UTC)
    clients = _load("clients.json")
    candidates = _load("candidates.json")
    decisions = _load("decisions.json")

    # --- clients + stated preferences
    prefs_by_client: dict[str, list[PreferenceIn]] = {}
    for c in clients:
        session.add(
            Client(
                id=_id("client", c["slug"]),
                name=c["name"],
                age=c["age"],
                location=c["location"],
                profile_summary=c["profile_summary"],
                created_at=now - timedelta(days=120),
            )
        )
        prefs_by_client[c["slug"]] = []
        for p in c["preferences"]:
            session.add(
                ClientPreference(
                    id=_id("pref", f"{c['slug']}:{p['attribute']}"),
                    client_id=_id("client", c["slug"]),
                    attribute=p["attribute"],
                    value=p["value"],
                    preference_type=PreferenceType(p["type"]),
                    source=PreferenceSource.onboarding,
                    created_at=now - timedelta(days=120),
                )
            )
            prefs_by_client[c["slug"]].append(PreferenceIn(p["attribute"], p["value"], p["type"]))

    # --- candidates
    for c in candidates:
        session.add(
            Candidate(
                id=_id("candidate", c["slug"]),
                name=c["name"],
                age=c["age"],
                location=c["location"],
                smokes=c["smokes"],
                drinks=c["drinks"],
                wants_children=c["wants_children"],
                willing_to_relocate=c["willing_to_relocate"],
                education=c["education"],
                education_tier=c["education_tier"],
                career=c["career"],
                career_level=c["career_level"],
                values_lifestyle=c["values_lifestyle"],
                bio=c["bio"],
                created_at=now - timedelta(days=150),
            )
        )
    session.flush()

    # --- decisions + saved feedback (signals classified by the same deterministic rules as the live flow)
    n_feedback = n_signals = 0
    for i, d in enumerate(decisions):
        when = now - timedelta(days=d["days_ago"], minutes=i)
        prefs = prefs_by_client[d["client"]]
        pairs = [(p.attribute, p.type) for p in prefs]
        fb = d.get("feedback")
        primary = None
        signals: list[StructuredSignal] = []
        if fb:
            for s in fb["signals"]:
                category = FeedbackCategory(s["category"])
                vtype = (
                    ViolationType(s["violation_type"])
                    if s.get("violation_type")
                    else classify_violation(category, pairs, s["attribute"])
                )
                signals.append(
                    StructuredSignal(  # validated exactly like model output
                        category=category,
                        attribute=s["attribute"],
                        violated_stated_preference=vtype in VIOLATION_TYPES_STATED,
                        violation_type=vtype,
                        confidence=s["confidence"],
                        explanation=explain(category, s["attribute"], vtype, prefs),
                        evidence=s["evidence"],
                    )
                )
            primary = next((s.category.value for s in signals if s.category != FeedbackCategory.unclear), None)
            primary = primary or signals[0].category.value

        decision_id = _id("decision", d["slug"])
        session.add(
            Decision(
                id=decision_id,
                client_id=_id("client", d["client"]),
                candidate_id=_id("candidate", d["candidate"]),
                matchmaker_id=d["matchmaker"],
                status=DecisionStatus(d["status"]),
                rejection_reason_category=primary,
                shared_at=when,
            )
        )
        if fb:
            session.flush()
            feedback = RejectionFeedback(
                id=_id("feedback", d["slug"]),
                decision_id=decision_id,
                client_id=_id("client", d["client"]),
                matchmaker_id=d["matchmaker"],
                raw_text=fb["note"],
                created_at=when,
            )
            for j, s in enumerate(signals):
                feedback.signals.append(
                    FeedbackSignal(
                        id=_id("signal", f"{d['slug']}:{j}"),
                        category=s.category.value,
                        observed_dimension=s.observed_dimension.value if s.observed_dimension else None,
                        attribute=s.attribute,
                        violated_stated_preference=s.violated_stated_preference,
                        violation_type=s.violation_type.value,
                        confidence=s.confidence.value,
                        explanation=s.explanation,
                        evidence=s.evidence,
                        created_at=when,
                    )
                )
            session.add(feedback)
            n_feedback += 1
            n_signals += len(signals)

    session.commit()

    # --- Preference Mirror: materialise suggestions, then apply matchmaker confirmations that are part of the story
    confirmed = 0
    for c in clients:
        client = session.get(Client, _id("client", c["slug"]))
        active = mirror_store.sync_client_mirror(session, client)
        session.commit()
        for rule_key in c.get("confirmed_mirror_rules", []):
            row = next((r for r, _d in active if r.rule_key == rule_key), None)
            if row is not None:
                mirror_store.confirm_signal(session, row.id)
                confirmed += 1

    return {
        "clients": len(clients),
        "candidates": len(candidates),
        "matchmakers": len({d["matchmaker"] for d in decisions}),
        "decisions": len(decisions),
        "accepted": sum(1 for d in decisions if d["status"] == "accepted"),
        "rejection_feedback": n_feedback,
        "feedback_signals": n_signals,
        "mirror_signals": session.scalar(select(func.count()).select_from(PreferenceMirrorSignal)) or 0,
        "mirror_confirmed": confirmed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="wipe all tables first")
    parser.add_argument("--if-empty", action="store_true", help="skip when data already exists")
    args = parser.parse_args()

    from app.db.session import get_session_factory

    with get_session_factory()() as session:
        summary = seed_database(session, reset=args.reset, if_empty=args.if_empty)
    if summary.get("skipped"):
        print("Database already seeded; skipping (use --reset to rebuild).")
        return
    print("Seeded:")
    for key, value in summary.items():
        print(f"  {key:20s} {value}")


if __name__ == "__main__":
    main()
