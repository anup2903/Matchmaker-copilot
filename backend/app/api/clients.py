import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import api_error
from app.core.preferences import describe_preference
from app.db.session import get_db
from app.models import Client, ClientPreference, Decision
from app.schemas.clients import ClientDetail, ClientSummary, DecisionOut, PreferenceOut
from app.services import mirror_store
from app.services.feedback_structurer import configured_phraser

router = APIRouter(tags=["clients"])

_TYPE_ORDER = {"dealbreaker": 0, "strong": 1, "soft": 2}


def get_client_or_404(db: Session, client_id: uuid.UUID) -> Client:
    client = db.get(Client, client_id)
    if client is None:
        raise api_error(404, "client_not_found", "Client not found.")
    return client


@router.get("/clients", response_model=list[ClientSummary])
def list_clients(db: Session = Depends(get_db)) -> list[Client]:
    return list(db.scalars(select(Client).order_by(Client.name)).all())


@router.get("/clients/{client_id}", response_model=ClientDetail)
def get_client(client_id: uuid.UUID, db: Session = Depends(get_db)) -> ClientDetail:
    client = get_client_or_404(db, client_id)
    prefs = db.scalars(select(ClientPreference).where(ClientPreference.client_id == client.id)).all()
    prefs = sorted(prefs, key=lambda p: (_TYPE_ORDER.get(p.preference_type.value, 9), p.attribute))
    decisions = db.scalars(
        select(Decision).where(Decision.client_id == client.id).order_by(Decision.shared_at.desc()).limit(12)
    ).all()
    cards = mirror_store.client_cards(db, client, phraser=configured_phraser())
    db.commit()
    return ClientDetail(
        id=client.id,
        name=client.name,
        age=client.age,
        location=client.location,
        profile_summary=client.profile_summary,
        preferences=[
            PreferenceOut(
                id=p.id,
                attribute=p.attribute,
                label=describe_preference(p.attribute, p.value),
                value=p.value,
                preference_type=p.preference_type.value,
                source=p.source.value,
                created_at=p.created_at,
            )
            for p in prefs
        ],
        recent_decisions=[
            DecisionOut(
                id=d.id,
                candidate_id=d.candidate_id,
                candidate_name=d.candidate.name,
                matchmaker_id=d.matchmaker_id,
                status=d.status.value,
                rejection_reason_category=d.rejection_reason_category,
                shared_at=d.shared_at,
            )
            for d in decisions
        ],
        preference_mirror=cards,
    )
