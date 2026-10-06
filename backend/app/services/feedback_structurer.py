"""Structure Feedback: free-text rejection note -> validated structured signals.

LLM is used for language -> structure only. Output is validated with Pydantic, evidence is checked to be a
verbatim quote of the note, and stated-preference flags are reconciled against the client's stored
preferences by deterministic code. One corrective retry on malformed output; one retry on timeouts.
"""

import re
import time
from dataclasses import dataclass

from app.core.config import Settings, get_settings
from app.schemas.feedback import StructuredFeedback
from app.services.domain import PreferenceIn
from app.services.llm.demo import DemoProvider
from app.services.llm.openai_compat import OpenAICompatibleProvider
from app.services.mirror_phrasing import Phraser, make_phraser
from app.services.llm.prompts import corrective_instruction
from app.services.llm.provider import (
    InvalidModelOutputError,
    LLMProvider,
    LLMUnavailableError,
)
from app.services.llm.signal_rules import reconcile

RETRY_DELAY_SECONDS = 3.0  # tests set this to 0
DEMO_NOTICE ="Demo mode: no LLM API key is configured, so a deterministic extractor was used."


@dataclass(frozen=True)
class StructureResult:
    feedback: StructuredFeedback
    demo_mode: bool
    provider: str
    notice: str | None = None


def get_provider(settings: Settings | None = None, force_demo: bool = False) -> LLMProvider:
    settings = settings or get_settings()
    if force_demo or not settings.llm_configured:
        return DemoProvider()
    return OpenAICompatibleProvider(
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        timeout=settings.llm_timeout_seconds,
        phrase_timeout=settings.llm_phrase_timeout_seconds,
    )


def configured_phraser() -> Phraser | None:
    """A Preference Mirror phraser when an LLM is configured, else None (deterministic templates)."""
    settings = get_settings()
    if not settings.llm_configured:
        return None
    return make_phraser(get_provider(settings))


def _canon(text: str) -> str:
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"[\s\"'.,;:!?—–-]+", " ", text).strip().lower()


def verify_evidence(feedback: StructuredFeedback, note: str) -> None:
    """Every evidence quote must literally appear in the note — the model may not invent evidence."""
    haystack = _canon(note)
    for s in feedback.signals:
        if _canon(s.evidence) not in haystack:
            raise InvalidModelOutputError(
                f'evidence "{s.evidence}" is not a verbatim quote from the rejection note', raw=s.evidence
            )


def structure_feedback(
    note: str, preferences: list[PreferenceIn], provider: LLMProvider
) -> StructureResult:
    correction: str | None = None
    invalid_retries = 1
    unavailable_retries = 1
    while True:
        try:
            result = provider.structure_rejection(note, preferences, correction)
            verify_evidence(result, note)
            break
        except InvalidModelOutputError as exc:
            if invalid_retries == 0:
                raise InvalidModelOutputError(
                    "The language model returned output that could not be validated, even after a retry.",
                    raw=exc.raw,
                ) from exc
            invalid_retries -= 1
            correction = corrective_instruction(exc.message)
        except LLMUnavailableError:
            if unavailable_retries == 0:
                raise
            unavailable_retries -= 1
            time.sleep(RETRY_DELAY_SECONDS)  # brief pause so a rate-limit (429) has a chance to clear

    return StructureResult(
        feedback=reconcile(result, preferences, note),
        demo_mode=provider.demo,
        provider=provider.name,
        notice=DEMO_NOTICE if provider.demo else None,
    )
