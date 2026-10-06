from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.clients import get_client_or_404
from app.api.errors import api_error
from app.db.session import get_db
from app.models import Candidate, MirrorStatus
from app.schemas.profile_check import PartyRef, ProfileCheckRequest, ProfileCheckResponse, ReasonOut
from app.services import context, mirror_store
from app.services.feedback_structurer import configured_phraser
from app.services.domain import MirrorSignalIn, Reason
from app.services.profile_checker import check_profile

router = APIRouter(tags=["profile-check"])

STATUS_LABELS = {"RED": "RED — BLOCKED", "AMBER": "AMBER — REVIEW", "GREEN": "GREEN — GOOD TO SHARE"}


def _reason(r: Reason) -> ReasonOut:
    return ReasonOut(code=r.code, message=r.message, source=r.source, evidence=r.evidence, refs=list(r.refs))


@router.post("/profile-check", response_model=ProfileCheckResponse)
def profile_check(body: ProfileCheckRequest, db: Session = Depends(get_db)) -> ProfileCheckResponse:
    client = get_client_or_404(db, body.client_id)
    candidate = db.get(Candidate, body.candidate_id)
    if candidate is None:
        raise api_error(404, "candidate_not_found", "Candidate not found.")

    prefs = context.load_preferences(db, client.id)
    signals = context.flatten_signals(context.load_feedback(db, client.id))
    active = mirror_store.sync_client_mirror(db, client, phraser=configured_phraser())
    db.commit()

    mirror_in = [
        MirrorSignalIn(
            id=str(row.id),
            rule_key=row.rule_key,
            status=row.status.value,
            confidence=row.confidence,
            possible_pattern=row.possible_pattern,
            supporting_count=len(row.evidence_feedback_ids or []),
            confirmed_at=row.confirmed_at,
        )
        for row, _draft in active
        if row.status in (MirrorStatus.suggested, MirrorStatus.confirmed)
    ]
    result = check_profile(
        client=context.client_in(client),
        preferences=prefs,
        candidate=context.candidate_in(candidate),
        rejection_signals=signals,
        mirror_signals=mirror_in,
    )

    mirror_card = None
    if result.mirror_signal_id:
        for row, draft in active:
            if str(row.id) == result.mirror_signal_id:
                mirror_card = mirror_store.to_card(row, draft)
                break

    return ProfileCheckResponse(
        status=result.status,
        status_label=STATUS_LABELS[result.status],
        summary=result.summary,
        client=PartyRef(id=client.id, name=client.name),
        candidate=PartyRef(id=candidate.id, name=candidate.name),
        blocking_reasons=[_reason(r) for r in result.blocking_reasons],
        warnings=[_reason(r) for r in result.warnings],
        positive_signals=[_reason(r) for r in result.positive_signals],
        notes=[_reason(r) for r in result.notes],
        preference_mirror=mirror_card,
    )
