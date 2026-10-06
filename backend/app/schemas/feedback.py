from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.core.preferences import (
    DIMENSION_SHORT_LABELS,
    VIOLATION_TYPES_STATED,
    Confidence,
    FeedbackCategory,
    ObservedDimension,
    ViolationType,
    infer_dimension,
)
from app.schemas.mirror import MirrorCard


class StructuredSignal(BaseModel):
    """One structured reason extracted from a rejection note.

    This is the contract every model output is validated against — raw LLM JSON is never trusted.
    """

    model_config = ConfigDict(extra="forbid")

    category: FeedbackCategory
    # Short label for the specific reason. It is ALWAYS derived from `observed_dimension` (a fixed list), so
    # whatever the model writes here is ignored: labels stay consistent and nothing free-form leaks in.
    attribute: str = Field(default="", max_length=80, description="Derived from observed_dimension")
    # The single most specific tag the model picks from a fixed list. If it is omitted, the server fills a
    # deterministic value from (category, attribute, evidence) so grouping still works.
    observed_dimension: ObservedDimension | None = None
    violated_stated_preference: bool
    violation_type: ViolationType
    confidence: Confidence
    explanation: str = Field(min_length=1, max_length=400, description="1-2 sentences")
    evidence: str = Field(min_length=1, max_length=300, description="Verbatim quote from the note")

    @model_validator(mode="after")
    def _finalise(self) -> "StructuredSignal":
        expected = self.violation_type in VIOLATION_TYPES_STATED
        if self.violated_stated_preference != expected:
            raise ValueError(
                f"violated_stated_preference={self.violated_stated_preference} is inconsistent with "
                f"violation_type='{self.violation_type.value}'"
            )
        if self.observed_dimension is None:
            self.observed_dimension = infer_dimension(self.category, self.attribute, self.evidence)
        self.attribute = DIMENSION_SHORT_LABELS.get(self.observed_dimension.value, self.category.value.replace("_", " "))
        return self


class StructuredFeedback(BaseModel):
    """What the LLM (or the demo extractor) returns: one signal per distinct reason."""

    model_config = ConfigDict(extra="forbid")

    signals: list[StructuredSignal] = Field(min_length=1, max_length=6)


class FeedbackStructureRequest(BaseModel):
    client_id: UUID
    rejection_note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
    # Lets the UI fall back to the deterministic demo extractor after an LLM failure.
    use_demo_mode: bool = False


class FeedbackStructureResponse(BaseModel):
    signals: list[StructuredSignal]
    demo_mode: bool
    provider: str  # "demo" | "llm"
    notice: str | None = None


class FeedbackSaveRequest(BaseModel):
    client_id: UUID
    rejection_note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
    matchmaker_id: Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9_-]{1,20}$")] = "A"
    candidate_id: UUID | None = None
    # Matchmaker-reviewed (and possibly edited) signals — only saved feedback feeds history.
    signals: list[StructuredSignal] = Field(min_length=1, max_length=6)


class FeedbackSaveResponse(BaseModel):
    feedback_id: UUID
    decision_id: UUID | None
    signal_count: int
    created_at: datetime
    preference_mirror: list[MirrorCard]
