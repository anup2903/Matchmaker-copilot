"""Provider adapter: business logic depends on `LLMProvider`, never on a specific vendor."""

from abc import ABC, abstractmethod

from app.schemas.feedback import StructuredFeedback
from app.services.domain import PreferenceIn


class LLMProviderError(Exception):
    code = "llm_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class LLMUnavailableError(LLMProviderError):
    """Timeout, network failure, auth failure or provider 5xx — the caller may retry or fall back to demo mode."""

    code = "llm_unavailable"


class InvalidModelOutputError(LLMProviderError):
    """Model replied, but not with JSON that satisfies our Pydantic contract."""

    code = "llm_invalid_output"

    def __init__(self, message: str, raw: str = ""):
        super().__init__(message)
        self.raw = raw


class LLMProvider(ABC):
    name: str = "provider"
    demo: bool = False

    @abstractmethod
    def structure_rejection(
        self,
        note: str,
        client_preferences: list[PreferenceIn],
        correction: str | None = None,
    ) -> StructuredFeedback:
        """Turn a free-text rejection note into validated structured signals.

        `correction` is an optional corrective instruction appended on a retry after malformed output.
        Implementations must raise InvalidModelOutputError / LLMUnavailableError rather than return junk.
        """

    def phrase_pattern(self, instruction: str) -> str | None:
        """Write a single Preference Mirror pattern sentence from supplied structured facts.

        Returns the sentence, or None to signal "use the deterministic template instead" (the default, so
        the demo provider and any provider that cannot phrase simply fall back). The caller validates the
        returned sentence and falls back on anything suspicious — the model only ever rephrases facts it is
        given, never invents evidence.
        """
        return None
