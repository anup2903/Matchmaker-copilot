"""Optional LLM phrasing for the Preference Mirror "possible pattern" sentence.

The engine (preference_mirror.py) always produces a deterministic template sentence. This layer may replace
it with a more natural one written by the LLM — but only the *wording* changes: the counts, evidence and
confidence are computed deterministically and are never handed to the model to restate. Anything the model
returns is validated (hedged language, no invented numbers, no overclaiming) and rejected back to the
template on the slightest doubt, so a phrasing failure can never corrupt or inflate a card.
"""

from collections.abc import Callable

from app.services.llm.provider import LLMProvider
from app.services.preference_mirror import FORBIDDEN_PHRASES, MirrorCardDraft

MAX_LEN = 320
_HEDGES = ("may", "appears", "could", "might", "seems", "suggest", "can ", "possible")

# A phraser turns a draft into its final "possible pattern" sentence.
Phraser = Callable[[MirrorCardDraft], str]


def _build_instruction(draft: MirrorCardDraft) -> str:
    return (
        "Rewrite the possible pattern as ONE natural, cautious sentence for a matchmaker.\n"
        f"What the client says: {draft.stated_text}\n"
        f"What their decisions suggest: {draft.observed_summary}\n"
        f"Baseline meaning to preserve: {draft.possible_pattern}\n"
        "Keep the same meaning. Do not include any numbers, names or facts beyond the baseline. "
        "One sentence only."
    )


def is_acceptable(sentence: str, draft: MirrorCardDraft) -> bool:
    text = sentence.strip()
    if not text or len(text) > MAX_LEN:
        return False
    low = text.lower()
    if any(bad in low for bad in FORBIDDEN_PHRASES):
        return False
    if any(ch.isdigit() for ch in text):  # counts belong in the evidence summary, not the sentence
        return False
    if not any(h in low for h in _HEDGES):  # must stay tentative
        return False
    return True


def phrase_draft(draft: MirrorCardDraft, provider: LLMProvider) -> str:
    """Final pattern sentence: LLM wording when it passes validation, else the deterministic template."""
    if draft.mixed_evidence:
        # The template carefully frames the conflicting evidence; keep it verbatim.
        return draft.possible_pattern
    try:
        candidate = provider.phrase_pattern(_build_instruction(draft))
    except Exception:  # noqa: BLE001 - phrasing is best-effort and must never break a page
        candidate = None
    if candidate and is_acceptable(candidate, draft):
        return candidate.strip()
    return draft.possible_pattern


def make_phraser(provider: LLMProvider | None) -> Phraser | None:
    """A phraser bound to a provider, or None to keep deterministic templates everywhere."""
    if provider is None:
        return None
    return lambda draft: phrase_draft(draft, provider)
