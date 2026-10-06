from collections.abc import Callable
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.clients import get_client_or_404
from app.api.errors import api_error
from app.core.preferences import FeedbackCategory
from app.db.session import get_db
from app.models import Candidate, Decision, DecisionStatus, FeedbackSignal, RejectionFeedback
from app.schemas.feedback import (
    FeedbackSaveRequest,
    FeedbackSaveResponse,
    FeedbackStructureRequest,
    FeedbackStructureResponse,
)
from app.services import context, mirror_store
from app.services.feedback_structurer import configured_phraser, get_provider, structure_feedback
from app.services.llm.demo import SAMPLE_NOTES
from app.services.llm.provider import InvalidModelOutputError, LLMProvider, LLMUnavailableError

router = APIRouter(tags=["feedback"])

ProviderFactory = Callable[[bool], LLMProvider]


def provider_factory() -> ProviderFactory:
    """Dependency: lets tests swap the LLM provider without touching business logic."""
    return lambda force_demo: get_provider(force_demo=force_demo)


@router.get("/feedback/samples")
def sample_notes() -> list[dict[str, str]]:
    return SAMPLE_NOTES


@router.post("/feedback/structure", response_model=FeedbackStructureResponse)
def structure(
    body: FeedbackStructureRequest,
    db: Session = Depends(get_db),
    factory: ProviderFactory = Depends(provider_factory),
) -> FeedbackStructureResponse:
    client = get_client_or_404(db, body.client_id)
    prefs = context.load_preferences(db, client.id)
    provider = factory(body.use_demo_mode)
    try:
        result = structure_feedback(body.rejection_note, prefs, provider)
    except LLMUnavailableError as exc:
        raise api_error(503, exc.code, exc.message, fallback_available=True) from exc
    except InvalidModelOutputError as exc:
        raise api_error(
            502,
            exc.code,
            "The language model returned output that could not be validated. Nothing was saved.",
            fallback_available=True,
        ) from exc
    return FeedbackStructureResponse(
        signals=result.feedback.signals,
        demo_mode=result.demo_mode,
        provider=result.provider,
        notice=result.notice,
    )


@router.post("/feedback/save", response_model=FeedbackSaveResponse, status_code=201)
def save(body: FeedbackSaveRequest, db: Session = Depends(get_db)) -> FeedbackSaveResponse:
    """Persist matchmaker-confirmed feedback. Only saved feedback joins the historical signal set."""
    client = get_client_or_404(db, body.client_id)
    now = datetime.now(UTC)

    decision: Decision | None = None
    primary = next(
        (s.category for s in body.signals if s.category != FeedbackCategory.unclear), body.signals[0].category
    ).value
    if body.candidate_id is not None:
        if db.get(Candidate, body.candidate_id) is None:
            raise api_error(404, "candidate_not_found", "Candidate not found.")
        decision = db.scalars(
            select(Decision)
            .where(Decision.client_id == client.id, Decision.candidate_id == body.candidate_id)
            .order_by(Decision.shared_at.desc())
        ).first()
        if decision is None:
            decision = Decision(
                client_id=client.id,
                candidate_id=body.candidate_id,
                matchmaker_id=body.matchmaker_id,
                status=DecisionStatus.rejected,
                rejection_reason_category=primary,
                shared_at=now,
            )
            db.add(decision)
        else:
            decision.status = DecisionStatus.rejected
            decision.rejection_reason_category = primary
        db.flush()

    feedback = RejectionFeedback(
        decision_id=decision.id if decision else None,
        client_id=client.id,
        matchmaker_id=body.matchmaker_id,
        raw_text=body.rejection_note,
        created_at=now,
    )
    for s in body.signals:
        feedback.signals.append(
            FeedbackSignal(
                category=s.category.value,
                observed_dimension=s.observed_dimension.value if s.observed_dimension else None,
                attribute=s.attribute,
                violated_stated_preference=s.violated_stated_preference,
                violation_type=s.violation_type.value,
                confidence=s.confidence.value,
                explanation=s.explanation,
                evidence=s.evidence,
                created_at=now,
            )
        )
    db.add(feedback)
    db.flush()

    cards = mirror_store.client_cards(db, client, phraser=configured_phraser())  # new evidence may open or strengthen a suggestion
    db.commit()
    return FeedbackSaveResponse(
        feedback_id=feedback.id,
        decision_id=decision.id if decision else None,
        signal_count=len(body.signals),
        created_at=now,
        preference_mirror=cards,
    )
