"""Deterministic guardrails applied to every extracted signal, whichever provider produced it.

The LLM proposes; these rules make sure "violated a stated preference" only ever means the client
really has a semantically relevant preference on file — and that "dealbreaker" is only ever used when
the client has a stored dealbreaker for it. (Dealbreaker *blocking* lives in profile_checker.py.)
"""

import re

from app.core.preferences import (
    STRENGTH_WORDS,
    VIOLATION_TYPES_STATED,
    Confidence,
    FeedbackCategory,
    relevant_attributes,
    ViolationType,
    classify_violation,
    describe_preference,
)
from app.schemas.feedback import StructuredFeedback, StructuredSignal
from app.services.domain import PreferenceIn

_TYPE_RANK = {"dealbreaker": 0, "strong": 1, "soft": 2}


def _pref_pairs(prefs: list[PreferenceIn]) -> list[tuple[str, str]]:
    return [(p.attribute, str(p.type)) for p in prefs if not p.attribute.startswith("mirror:")]


def relevant_preference(
    category: FeedbackCategory, prefs: list[PreferenceIn], attribute: str = ""
) -> PreferenceIn | None:
    attrs = relevant_attributes(category, attribute)
    matches = [p for p in prefs if p.attribute in attrs]
    return min(matches, key=lambda p: _TYPE_RANK.get(str(p.type), 9), default=None)


def explain(category: FeedbackCategory, attribute: str, vtype: ViolationType, prefs: list[PreferenceIn]) -> str:
    if vtype in VIOLATION_TYPES_STATED:
        pref = relevant_preference(category, prefs, attribute)
        if pref is not None:
            return (
                f"The note cites {attribute}, and the client has recorded “"
                f"{describe_preference(pref.attribute, pref.value)}” as {STRENGTH_WORDS[str(pref.type)]}."
            )
    if vtype == ViolationType.new_signal:
        return f"The note cites {attribute}; no matching stated preference is on file, so it is recorded as a new signal."
    if vtype == ViolationType.not_a_preference_violation:
        return "The note describes timing or availability rather than a mismatch with the client's preferences."
    return "The note does not say what specifically did not work, so no reason is inferred."


# Wording that shows the writer was unsure. The model is told to preserve uncertainty but tends to say "high"
# anyway, so we cap confidence deterministically from the clause the evidence quote sits in.
_HEDGE_STRONG = re.compile(r"\b(i guess|hard to say|maybe|perhaps|idk|don'?t know|no idea|not certain)\b", re.I)
_HEDGE_SOFT = re.compile(r"\b(not sure|kinda|kind of|sort of|a bit|somewhat|probably|hmm|i think|might)\b", re.I)
_CLAUSE_BREAK = re.compile(r"[.!?;,]|\bbut\b", re.I)
_RANK = {Confidence.low: 0, Confidence.medium: 1, Confidence.high: 2}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("’", "'").replace("‘", "'")).strip().lower()


def _clause_for(note: str, evidence: str) -> str:
    """The part of `note` the evidence quote sits in: every clause (split on punctuation / 'but') it overlaps.

    Falls back to the whole note only if the quote cannot be located at all.
    """
    text, needle = _norm(note), _norm(evidence)
    start = text.find(needle) if needle else -1
    if start < 0:
        return text
    end = start + len(needle)
    pieces, pos = [], 0
    for m in _CLAUSE_BREAK.finditer(text):
        pieces.append((pos, m.start()))
        pos = m.end()
    pieces.append((pos, len(text)))
    overlapping = [text[a:b] for a, b in pieces if a < end and b > start]
    return " ".join(overlapping) if overlapping else text


def cap_confidence(signal: StructuredSignal, note: str) -> StructuredSignal:
    """Hedged wording can lower confidence, never raise it."""
    clause = _clause_for(note, signal.evidence)
    if _HEDGE_STRONG.search(clause):
        ceiling = Confidence.low
    elif _HEDGE_SOFT.search(clause):
        ceiling = Confidence.medium
    else:
        return signal
    if _RANK[signal.confidence] <= _RANK[ceiling]:
        return signal
    return signal.model_copy(update={"confidence": ceiling})


def reconcile(feedback: StructuredFeedback, prefs: list[PreferenceIn], note: str = "") -> StructuredFeedback:
    """Align violation_type with the client's stored preferences, and temper confidence on hedged wording."""
    pairs = _pref_pairs(prefs)
    fixed: list[StructuredSignal] = []
    for s in feedback.signals:
        if s.violation_type in (ViolationType.not_a_preference_violation, ViolationType.unclear):
            fixed.append(s)
            continue
        expected = classify_violation(s.category, pairs, s.attribute)
        if s.violation_type != expected:
            # The stored preferences decide stated-vs-new and the strength; the model keeps category/evidence.
            s = s.model_copy(
                update={
                    "violation_type": expected,
                    "violated_stated_preference": expected in VIOLATION_TYPES_STATED,
                    "explanation": explain(s.category, s.attribute, expected, prefs),
                }
            )
        fixed.append(cap_confidence(s, note) if note else s)
    return StructuredFeedback(signals=fixed)
