from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Candidate
from app.schemas.clients import CandidateOut

router = APIRouter(tags=["candidates"])


@router.get("/candidates", response_model=list[CandidateOut])
def list_candidates(db: Session = Depends(get_db)) -> list[Candidate]:
    return list(db.scalars(select(Candidate).order_by(Candidate.name)).all())
