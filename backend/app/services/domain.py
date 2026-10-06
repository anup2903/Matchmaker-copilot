"""Plain, framework-free inputs/outputs for the pure business-logic services.

The profile checker and Preference Mirror engine never touch the database or an LLM; the API layer
loads rows into these dataclasses and hands them over. That keeps the rules unit-testable.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

# A feedback signal only counts as "recent" within this window.
RECENT_DAYS = 180


def as_utc(dt: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; treat them as UTC so comparisons are safe."""
    if dt is None:
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


@dataclass(frozen=True)
class ClientIn:
    id: str
    name: str
    location: str | None = None


@dataclass(frozen=True)
class PreferenceIn:
    attribute: str
    value: dict[str, Any]
    type: str  # dealbreaker | strong | soft
    source: str = "onboarding"


@dataclass(frozen=True)
class CandidateIn:
    id: str
    name: str
    age: int | None = None
    location: str | None = None
    smokes: bool | None = None
    drinks: bool | None = None
    wants_children: bool | None = None
    willing_to_relocate: bool | None = None
    education: str | None = None
    education_tier: str | None = None  # prestigious | standard
    career: str | None = None
    career_level: str | None = None  # senior | mid | early
    values_lifestyle: dict[str, Any] = field(default_factory=dict)

    @property
    def lifestyle_tags(self) -> list[str]:
        return [str(t).lower() for t in (self.values_lifestyle or {}).get("tags", [])]


@dataclass(frozen=True)
class SignalIn:
    """One saved, human-confirmed feedback signal."""

    feedback_id: str
    category: str
    attribute: str
    evidence: str
    violation_type: str
    confidence: str
    created_at: datetime
    observed_dimension: str | None = None
    decision_id: str | None = None


@dataclass(frozen=True)
class FeedbackIn:
    """One saved rejection note with its signals."""

    id: str
    created_at: datetime
    signals: tuple[SignalIn, ...]
    decision_id: str | None = None


@dataclass(frozen=True)
class AcceptedIn:
    decision_id: str
    candidate: CandidateIn
    decided_at: datetime | None = None


@dataclass(frozen=True)
class MirrorSignalIn:
    """Persisted Preference Mirror state, as seen by the profile checker."""

    id: str
    rule_key: str
    status: str  # suggested | confirmed
    confidence: str
    possible_pattern: str
    supporting_count: int = 0
    confirmed_at: datetime | None = None


@dataclass(frozen=True)
class Reason:
    code: str
    message: str
    source: str  # dealbreaker | stated_preference | past_rejection | observed_pattern | confirmed_signal
    evidence: str
    refs: tuple[str, ...] = ()


@dataclass
class CheckResult:
    status: str  # RED | AMBER | GREEN
    summary: str
    blocking_reasons: list[Reason] = field(default_factory=list)
    warnings: list[Reason] = field(default_factory=list)
    positive_signals: list[Reason] = field(default_factory=list)
    notes: list[Reason] = field(default_factory=list)
    mirror_signal_id: str | None = None
