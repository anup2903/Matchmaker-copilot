from app.core.preferences import (
    DIMENSION_LABELS,
    STRENGTH_WORDS,
    FeedbackCategory,
    ObservedDimension,
    ViolationType,
    describe_preference,
)
from app.services.domain import PreferenceIn

_DIMENSION_LINES = "\n".join(f"    - {d.value}: {DIMENSION_LABELS[d.value]}" for d in ObservedDimension)

SYSTEM_PROMPT = f"""You are extracting structured facts from a matchmaker's free-text note about why a client rejected a candidate profile.

Rules:
- Extract only what the note supports. Do not infer facts that are absent. Never invent a candidate attribute or a reason that is not in the note.
- Return one signal per distinct reason (an array). Do not blend several reasons into one label.
- category must be one of: {", ".join(c.value for c in FeedbackCategory)}.
- observed_dimension is the single most specific tag for what the reason is really about. Pick exactly one from this fixed list (never invent one):
{_DIMENSION_LINES}
  Choose the precise tag: e.g. a complaint about which college someone attended is "education_prestige", not "career_ambition"; drinking/partying is "lifestyle_social". Use "other" or "unclear" only when nothing fits.
- violation_type must be one of: {", ".join(v.value for v in ViolationType)}.
  * dealbreaker / stated_preference / soft_preference: use ONLY when the reason is semantically about one of the client preferences supplied below, matching that preference's strength.
  * new_signal: the reason is clear but none of the supplied preferences covers it.
  * not_a_preference_violation: the reason is practical (timing, availability) and not about the profile.
  * unclear: the note gives insufficient evidence. Use category "unclear" and confidence "low".
- violated_stated_preference is true only for dealbreaker, stated_preference and soft_preference; otherwise false.
- confidence: "high" only when the note states the reason explicitly and without hedging. Use "medium" when the wording is tentative ("kinda", "not sure", "a bit") and "low" when it is vague or guessed ("I guess", "maybe", "hard to say"). Preserve uncertainty instead of guessing.
- A complaint about how the candidate treats or talks about other people (arrogance, rudeness, judgemental attitude) is communication_personality / communication_style or emotional_maturity, not intellectual_fit and not an education preference — unless the note is itself about the candidate's intelligence or education.
- evidence: a short quote copied verbatim from the note.
- explanation: 1-2 sentences grounded in the note and the supplied preferences.
- Never infer sensitive personal attributes (religion, caste, health, sexual orientation, etc.) and never comment on physical appearance.
- You only label why a past profile was rejected. You do not decide whether anything is a hard dealbreaker for blocking purposes.
- Output JSON only, matching the schema: {{"signals": [...]}}."""


def build_user_payload(note: str, preferences: list[PreferenceIn]) -> str:
    stated = [p for p in preferences if p.type != "dealbreaker" and not p.attribute.startswith("mirror:")]
    dealbreakers = [p for p in preferences if p.type == "dealbreaker"]

    def line(p: PreferenceIn) -> str:
        return f"- {describe_preference(p.attribute, p.value)} ({STRENGTH_WORDS.get(p.type, p.type)})"

    stated_block = "\n".join(line(p) for p in stated) or "- (none recorded)"
    deal_block = "\n".join(f"- {describe_preference(p.attribute, p.value)}" for p in dealbreakers) or "- (none recorded)"
    return (
        f"Client preferences:\n{stated_block}\n\n"
        f"Dealbreakers:\n{deal_block}\n\n"
        f'Rejection note:\n"""\n{note}\n"""'
    )


def corrective_instruction(problem: str) -> str:
    return (
        "Your previous reply could not be accepted: "
        f"{problem}\n"
        'Reply again with ONLY valid JSON of the form {"signals": [...]}, following every rule above. '
        "Each evidence value must be copied verbatim from the rejection note."
    )
