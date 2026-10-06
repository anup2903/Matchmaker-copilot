import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.clients import get_client_or_404
from app.api.errors import api_error
from app.db.session import get_db
from app.schemas.mirror import MirrorCard, MirrorResponse
from app.services import mirror_store
from app.services.feedback_structurer import configured_phraser

router = APIRouter(tags=["preference-mirror"])


@router.get("/clients/{client_id}/preference-mirror", response_model=MirrorResponse)
def get_mirror(client_id: uuid.UUID, db: Session = Depends(get_db)) -> MirrorResponse:
    client = get_client_or_404(db, client_id)
    cards = mirror_store.client_cards(db, client, phraser=configured_phraser())
    db.commit()
    return MirrorResponse(
        client_id=client.id,
        suggestions=[c for c in cards if c.status == "suggested"],
        confirmed=[c for c in cards if c.status == "confirmed"],
    )


@router.post("/preference-mirror/{signal_id}/confirm", response_model=MirrorCard)
def confirm(signal_id: uuid.UUID, db: Session = Depends(get_db)) -> MirrorCard:
    try:
        return mirror_store.confirm_signal(db, signal_id)
    except mirror_store.MirrorNotFoundError as exc:
        raise api_error(404, "mirror_signal_not_found", "Preference Mirror signal not found.") from exc
    except mirror_store.MirrorConflictError as exc:
        raise api_error(409, "mirror_conflict", str(exc)) from exc


@router.post("/preference-mirror/{signal_id}/dismiss", response_model=MirrorCard)
def dismiss(signal_id: uuid.UUID, db: Session = Depends(get_db)) -> MirrorCard:
    try:
        return mirror_store.dismiss_signal(db, signal_id)
    except mirror_store.MirrorNotFoundError as exc:
        raise api_error(404, "mirror_signal_not_found", "Preference Mirror signal not found.") from exc
    except mirror_store.MirrorConflictError as exc:
        raise api_error(409, "mirror_conflict", str(exc)) from exc
