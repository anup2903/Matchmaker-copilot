"""Persistence for Preference Mirror suggestions: materialise, confirm, dismiss.

The engine (preference_mirror.py) is pure. This module turns its drafts into `preference_mirror_signals`
rows so a matchmaker's decision (confirm / dismiss) is durable and auditable:

* confirm  -> row marked human_confirmed + a *soft* client preference (source=human_confirmed) is stored.
* dismiss  -> row marked dismissed, raw feedback evidence is kept, nothing becomes a preference.
              It only resurfaces if materially stronger evidence appears (REAPPEAR_EXTRA_REJECTIONS more).
Nothing here ever creates a dealbreaker or edits an onboarding preference.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Client, ClientPreference, MirrorStatus, PreferenceMirrorSignal, PreferenceSource
from app.core.preferences import PreferenceType
from app.schemas.mirror import EvidenceItemOut, MirrorCard
from app.services import context
from app.services.mirror_phrasing import Phraser
from app.services.preference_mirror import (
    MIRROR_RULES,
    REAPPEAR_EXTRA_REJECTIONS,
    MirrorCardDraft,
    compute_mirror_cards,
)

_CONF_ORDER = {"high": 0, "medium": 1, "low": 2}


class MirrorNotFoundError(Exception):
    pass


class MirrorConflictError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def sync_client_mirror(
    db: Session, client: Client, now: datetime | None = None, phraser: Phraser | None = None
) -> list[tuple[PreferenceMirrorSignal, MirrorCardDraft | None]]:
    """Reconcile engine output with stored rows. Returns active (suggested/confirmed) rows with their drafts.

    `phraser` (optional) rewrites a new or materially-changed suggestion's pattern sentence via the LLM; it
    is only invoked when the evidence actually changed, so steady-state page views make no model calls.
    """
    now = now or _now()
    prefs = context.load_preferences(db, client.id)
    feedback = context.load_feedback(db, client.id)
    accepted = context.load_accepted(db, client.id)
    drafts = {d.rule_key: d for d in compute_mirror_cards(prefs, feedback, accepted, client.location, now)}

    rows = db.scalars(
        select(PreferenceMirrorSignal)
        .where(PreferenceMirrorSignal.client_id == client.id)
        .order_by(PreferenceMirrorSignal.created_at, PreferenceMirrorSignal.updated_at)
    ).all()
    latest: dict[str, PreferenceMirrorSignal] = {}
    for r in rows:
        latest[r.rule_key] = r

    for key, draft in drafts.items():
        row = latest.get(key)
        if row is None or (
            row.status == MirrorStatus.dismissed
            and draft.supporting_count >= len(row.evidence_feedback_ids or []) + REAPPEAR_EXTRA_REJECTIONS
        ):
            row = PreferenceMirrorSignal(
                client_id=client.id,
                rule_key=key,
                status=MirrorStatus.suggested,
                human_confirmed=False,
                created_at=now,
                updated_at=now,
            )
            _apply_draft(row, draft, _pattern_text(draft, None, phraser))
            db.add(row)
            latest[key] = row
        elif row.status == MirrorStatus.suggested:
            _apply_draft(row, draft, _pattern_text(draft, row, phraser))  # keep the open suggestion current
        # confirmed rows are frozen (what the matchmaker actually confirmed); dismissed rows stay hidden

    db.flush()
    active = [
        (row, drafts.get(key))
        for key, row in latest.items()
        if row.status in (MirrorStatus.suggested, MirrorStatus.confirmed)
    ]
    active.sort(key=lambda t: (t[0].status != MirrorStatus.confirmed, _CONF_ORDER.get(t[0].confidence, 9)))
    return active


def _evidence_changed(row: PreferenceMirrorSignal | None, draft: MirrorCardDraft) -> bool:
    if row is None:
        return True
    return (
        row.confidence != draft.confidence
        or list(row.evidence_feedback_ids or []) != list(draft.supporting_feedback_ids)
        or list(row.evidence_decision_ids or []) != list(draft.similar_accepted_decision_ids)
    )


def _pattern_text(draft: MirrorCardDraft, row: PreferenceMirrorSignal | None, phraser: Phraser | None) -> str:
    """The sentence to store: re-phrase only when evidence changed, else reuse what's already stored."""
    if phraser is None:
        return draft.possible_pattern
    if _evidence_changed(row, draft):
        return phraser(draft)
    return row.possible_pattern if row else draft.possible_pattern


def _apply_draft(row: PreferenceMirrorSignal, draft: MirrorCardDraft, pattern_text: str) -> None:
    changed = (
        row.possible_pattern != pattern_text
        or row.confidence != draft.confidence
        or list(row.evidence_feedback_ids or []) != list(draft.supporting_feedback_ids)
        or list(row.evidence_decision_ids or []) != list(draft.similar_accepted_decision_ids)
    )
    row.observed_attribute = draft.observed_attribute
    row.stated_attribute = draft.stated_attribute
    row.possible_pattern = pattern_text
    row.confidence = draft.confidence
    row.evidence_feedback_ids = list(draft.supporting_feedback_ids)
    row.evidence_decision_ids = list(draft.similar_accepted_decision_ids)
    if changed and row.id is not None:
        row.updated_at = _now()


def to_card(row: PreferenceMirrorSignal, draft: MirrorCardDraft | None) -> MirrorCard:
    rule = MIRROR_RULES.get(row.rule_key)
    frozen_ids = set(row.evidence_feedback_ids or []) | set(row.evidence_decision_ids or [])
    evidence: list[EvidenceItemOut] = []
    if draft is not None:
        items = draft.evidence
        if row.status == MirrorStatus.confirmed:  # confirmed cards show the evidence that was confirmed
            items = tuple(e for e in items if e.ref_id in frozen_ids)
        evidence = [
            EvidenceItemOut(
                kind=e.kind,
                ref_id=e.ref_id,
                text=e.text,
                date=e.date,
                highlight=e.highlight,
                highlight_label=e.highlight_label,
            )
            for e in items
        ]
    return MirrorCard(
        id=row.id,
        client_id=row.client_id,
        rule_key=row.rule_key,
        status=row.status.value,
        human_confirmed=row.human_confirmed,
        stated_attribute=row.stated_attribute,
        stated_text=draft.stated_text if draft else (rule.stated_template.format(strength="important") if rule else row.stated_attribute),
        observed_attribute=row.observed_attribute,
        observed_summary=draft.observed_summary if draft else "",
        possible_pattern=row.possible_pattern,
        confidence=row.confidence,
        mixed_evidence=draft.mixed_evidence if draft else row.possible_pattern.startswith("Mixed evidence"),
        evidence_summary=draft.evidence_summary if draft else "",
        evidence=evidence,
        supporting_count=len(row.evidence_feedback_ids or []),
        confirmed_at=row.confirmed_at,
    )


def client_cards(db: Session, client: Client, phraser: Phraser | None = None) -> list[MirrorCard]:
    return [to_card(row, draft) for row, draft in sync_client_mirror(db, client, phraser=phraser)]


def _get_row(db: Session, signal_id: uuid.UUID) -> PreferenceMirrorSignal:
    row = db.get(PreferenceMirrorSignal, signal_id)
    if row is None:
        raise MirrorNotFoundError(str(signal_id))
    return row


def confirm_signal(db: Session, signal_id: uuid.UUID) -> MirrorCard:
    row = _get_row(db, signal_id)
    if row.status == MirrorStatus.dismissed:
        raise MirrorConflictError("This suggestion was dismissed and can no longer be confirmed.")
    client = db.get(Client, row.client_id)
    assert client is not None
    if row.status != MirrorStatus.confirmed:
        now = _now()
        row.status = MirrorStatus.confirmed
        row.human_confirmed = True
        row.confirmed_at = now
        row.updated_at = now
        _upsert_soft_preference(db, row, now)
        db.commit()
    return _card_for(db, client, row)


def dismiss_signal(db: Session, signal_id: uuid.UUID) -> MirrorCard:
    row = _get_row(db, signal_id)
    if row.status == MirrorStatus.confirmed:
        raise MirrorConflictError("A confirmed signal cannot be dismissed.")
    client = db.get(Client, row.client_id)
    assert client is not None
    if row.status != MirrorStatus.dismissed:
        now = _now()
        row.status = MirrorStatus.dismissed
        row.human_confirmed = False
        row.dismissed_at = now
        row.updated_at = now
        db.commit()  # evidence ids on the row are kept for auditability; no preference is created
    return to_card(row, None)


def _card_for(db: Session, client: Client, row: PreferenceMirrorSignal) -> MirrorCard:
    for r, draft in sync_client_mirror(db, client):
        if r.id == row.id:
            return to_card(r, draft)
    return to_card(row, None)


def _upsert_soft_preference(db: Session, row: PreferenceMirrorSignal, now: datetime) -> None:
    """A confirmed pattern becomes a SOFT preference only — never a dealbreaker."""
    rule = MIRROR_RULES[row.rule_key]
    attribute = f"mirror:{row.rule_key}"
    value = {
        "rule_key": row.rule_key,
        "description": f"Soft signal (confirmed): {rule.trait_phrase}",
        "mirror_signal_id": str(row.id),
        "evidence_feedback_ids": list(row.evidence_feedback_ids or []),
        "evidence_decision_ids": list(row.evidence_decision_ids or []),
        "confirmed_at": now.isoformat(),
    }
    existing = db.scalar(
        select(ClientPreference).where(
            ClientPreference.client_id == row.client_id, ClientPreference.attribute == attribute
        )
    )
    if existing:
        existing.value = value
        existing.preference_type = PreferenceType.soft
        existing.source = PreferenceSource.human_confirmed
    else:
        db.add(
            ClientPreference(
                client_id=row.client_id,
                attribute=attribute,
                value=value,
                preference_type=PreferenceType.soft,
                source=PreferenceSource.human_confirmed,
                created_at=now,
            )
        )
