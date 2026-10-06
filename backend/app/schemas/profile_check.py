from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.schemas.mirror import MirrorCard

ReasonSource = Literal["dealbreaker", "stated_preference", "past_rejection", "observed_pattern", "confirmed_signal"]


class ProfileCheckRequest(BaseModel):
    client_id: UUID
    candidate_id: UUID


class ReasonOut(BaseModel):
    code: str
    message: str
    source: ReasonSource
    evidence: str
    refs: list[str] = []


class PartyRef(BaseModel):
    id: UUID
    name: str


class ProfileCheckResponse(BaseModel):
    status: Literal["RED", "AMBER", "GREEN"]
    status_label: str
    summary: str
    client: PartyRef
    candidate: PartyRef
    blocking_reasons: list[ReasonOut]
    warnings: list[ReasonOut]
    positive_signals: list[ReasonOut]
    notes: list[ReasonOut]
    preference_mirror: MirrorCard | None = None
