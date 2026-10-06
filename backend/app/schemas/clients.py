from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.schemas.mirror import MirrorCard


class ClientSummary(BaseModel):
    id: UUID
    name: str
    age: int
    location: str


class PreferenceOut(BaseModel):
    id: UUID
    attribute: str
    label: str
    value: dict[str, Any]
    preference_type: str
    source: str
    created_at: datetime


class DecisionOut(BaseModel):
    id: UUID
    candidate_id: UUID
    candidate_name: str
    matchmaker_id: str
    status: str
    rejection_reason_category: str | None
    shared_at: datetime


class ClientDetail(BaseModel):
    id: UUID
    name: str
    age: int
    location: str
    profile_summary: str
    preferences: list[PreferenceOut]
    recent_decisions: list[DecisionOut]
    preference_mirror: list[MirrorCard]


class CandidateOut(BaseModel):
    id: UUID
    name: str
    age: int
    location: str
    smokes: bool | None
    drinks: bool | None
    wants_children: bool | None
    willing_to_relocate: bool | None
    education: str | None
    education_tier: str | None
    career: str | None
    career_level: str | None
    values_lifestyle: dict[str, Any]
    bio: str
