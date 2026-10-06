from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

ADVISORY_NOTE = (
    "Suggestion only. This pattern is inferred from saved feedback and does not change the client's "
    "preferences unless the matchmaker confirms it."
)


class EvidenceItemOut(BaseModel):
    kind: Literal["rejection", "accepted"]
    ref_id: str
    text: str
    date: datetime | None = None
    highlight: bool = False
    highlight_label: str | None = None


class MirrorCard(BaseModel):
    id: UUID
    client_id: UUID
    rule_key: str
    status: Literal["suggested", "confirmed", "dismissed"]
    human_confirmed: bool
    # "What the client says"
    stated_attribute: str
    stated_text: str
    # "What their decisions suggest"
    observed_attribute: str
    observed_summary: str
    possible_pattern: str
    confidence: Literal["high", "medium", "low"]
    mixed_evidence: bool
    evidence_summary: str
    evidence: list[EvidenceItemOut]
    supporting_count: int
    confirmed_at: datetime | None = None
    advisory_note: str = ADVISORY_NOTE


class MirrorResponse(BaseModel):
    client_id: UUID
    suggestions: list[MirrorCard]
    confirmed: list[MirrorCard]
