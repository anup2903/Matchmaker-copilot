"""Deterministic demo extractor — used when no LLM_API_KEY is configured.

* Seeded example notes (SAMPLE_NOTES) map to curated, hand-checked extractions.
* Any other note goes through a small keyword extractor that only returns what the text literally contains
  (verbatim evidence) and says "unclear" when nothing matches.

Whether a signal counts as a stated-preference violation is still decided from the client's stored
preferences (never hard-coded per note), so the same note reads differently for different clients.
"""

import re
from dataclasses import dataclass

from app.core.preferences import (
    VIOLATION_TYPES_STATED,
    Confidence,
    FeedbackCategory,
    ViolationType,
    classify_violation,
)
from app.schemas.feedback import StructuredFeedback, StructuredSignal
from app.services.domain import PreferenceIn
from app.services.llm.provider import LLMProvider
from app.services.llm.signal_rules import explain

C = FeedbackCategory

SAMPLE_NOTES: list[dict[str, str]] = [
    {
        "id": "intellectual-and-distance",
        "label": "Intellect + distance",
        "note": "He seemed nice, but I didn’t feel we’d connect intellectually. Also I’m not sure our lifestyles would work with the distance.",
    },
    {
        "id": "smoking",
        "label": "Smoking (explicit)",
        "note": "She mentioned she smokes socially. That’s a no for me — I need someone who doesn’t smoke.",
    },
    {
        "id": "multiple-reasons",
        "label": "Multiple reasons",
        "note": "Lives too far from me, and the age gap felt a bit large. He also mentioned he doesn’t want kids.",
    },
    {
        "id": "college-pedigree",
        "label": "Intellect + college",
        "note": "Didn’t seem intellectually aligned, and his college background wasn’t what I was hoping for.",
    },
    {
        "id": "new-signal",
        "label": "New signal",
        "note": "He was polite, but he spent most of the call talking about himself and never asked me a question.",
    },
    {
        "id": "ambiguous",
        "label": "Ambiguous",
        "note": "Just didn’t feel it. Hard to say why.",
    },
    {
        "id": "unrelated",
        "label": "Unrelated / timing",
        "note": "She got swamped with a work trip and asked to pause introductions for a few weeks.",
    },
]


@dataclass(frozen=True)
class Draft:
    category: FeedbackCategory
    attribute: str
    evidence: str  # verbatim from the note
    confidence: Confidence
    vtype: ViolationType | None = None  # forced type (unclear / not_a_preference_violation)


def _norm(note: str) -> str:
    return re.sub(r"\s+", " ", note.replace("’", "'").replace("‘", "'")).strip().lower()


_CURATED: dict[str, list[Draft]] = {
    _norm(SAMPLE_NOTES[0]["note"]): [
        Draft(C.intellectual_fit, "intellectual compatibility", "didn’t feel we’d connect intellectually", Confidence.high),
        Draft(C.location_distance, "distance", "not sure our lifestyles would work with the distance", Confidence.medium),
    ],
    _norm(SAMPLE_NOTES[1]["note"]): [
        Draft(C.smoking_alcohol, "smoking", "I need someone who doesn’t smoke", Confidence.high),
    ],
    _norm(SAMPLE_NOTES[2]["note"]): [
        Draft(C.location_distance, "distance", "Lives too far from me", Confidence.high),
        Draft(C.age, "age gap", "the age gap felt a bit large", Confidence.medium),
        Draft(C.children_family_plans, "children", "he doesn’t want kids", Confidence.high),
    ],
    _norm(SAMPLE_NOTES[3]["note"]): [
        Draft(C.intellectual_fit, "intellectual compatibility", "Didn’t seem intellectually aligned", Confidence.high),
        Draft(C.career_education, "college pedigree", "his college background wasn’t what I was hoping for", Confidence.medium),
    ],
    _norm(SAMPLE_NOTES[4]["note"]): [
        Draft(C.communication_personality, "conversation style", "never asked me a question", Confidence.medium),
    ],
    _norm(SAMPLE_NOTES[5]["note"]): [
        Draft(C.unclear, "overall fit", "Just didn’t feel it", Confidence.low, ViolationType.unclear),
    ],
    _norm(SAMPLE_NOTES[6]["note"]): [
        Draft(
            C.other,
            "timing / availability",
            "asked to pause introductions for a few weeks",
            Confidence.medium,
            ViolationType.not_a_preference_violation,
        ),
    ],
}

# (category, attribute, regex) — first match per category wins; order matters for ties.
_KEYWORD_RULES: list[tuple[FeedbackCategory, str, str]] = [
    (C.intellectual_fit, "intellectual compatibility", r"intellect|stimulating|depth of conversation"),
    (C.career_education, "college pedigree", r"college|pedigree|universit|degree|alma mater"),
    (C.career_education, "career", r"\bcareer\b|\bjob\b|salary|ambiti|profession"),
    (C.location_distance, "distance", r"distance|too far|far from|far away|different city|relocat"),
    (C.smoking_alcohol, "smoking", r"smok|cigarette|vape"),
    (C.smoking_alcohol, "drinking", r"\bdrink|alcohol"),
    (C.children_family_plans, "children", r"\bkids?\b|children"),
    (C.family_background, "family background", r"family background|his family|her family|\bparents\b"),
    (C.age, "age gap", r"\bage\b|too old|too young|older than|younger than"),
    (C.values_lifestyle, "lifestyle", r"lifestyle|\bvalues\b|part(?:y|ies)\b|nightlife"),
    (
        C.communication_personality,
        "communication style",
        r"communicat|personality|\brude\b|arrogan|self-absorbed|texting|never asked",
    ),
    (C.attraction_first_impression, "first impression", r"attract|chemistry|\bspark\b|first impression"),
]
_UNRELATED = re.compile(r"busy|work trip|business trip|swamped|schedule|pause|not ready|no time|on hold", re.I)
_HEDGE = re.compile(r"not sure|maybe|kind of|a bit|perhaps|i guess|hard to say|might", re.I)
_CLAUSE_SPLIT = re.compile(r"[.!?;]\s+|,\s+|\s+(?:but|also|and|plus|though)\s+")


def _clauses(note: str) -> list[str]:
    return [seg.strip(" .!?;,—-\"'“”") for seg in _CLAUSE_SPLIT.split(note) if seg and seg.strip(" .!?;,—-\"'“”")]


def _keyword_drafts(note: str) -> list[Draft]:
    clauses = _clauses(note)
    drafts: list[Draft] = []
    seen: set[FeedbackCategory] = set()
    for category, attribute, pattern in _KEYWORD_RULES:
        if category in seen:
            continue
        rx = re.compile(pattern, re.I)
        clause = next((c for c in clauses if rx.search(c)), None)
        if clause:
            seen.add(category)
            # demo extraction is deliberately conservative: never "high", hedged wording => "low"
            confidence = Confidence.low if _HEDGE.search(clause) else Confidence.medium
            drafts.append(Draft(category, attribute, clause, confidence))
    if drafts:
        drafts.sort(key=lambda d: note.find(d.evidence))
        return drafts[:6]
    unrelated = next((c for c in clauses if _UNRELATED.search(c)), None)
    if unrelated:
        return [
            Draft(C.other, "timing / availability", unrelated, Confidence.medium, ViolationType.not_a_preference_violation)
        ]
    evidence = clauses[0] if clauses else note.strip()
    return [Draft(C.unclear, "overall fit", evidence[:300], Confidence.low, ViolationType.unclear)]


def _to_signal(d: Draft, prefs: list[PreferenceIn]) -> StructuredSignal:
    if d.vtype is not None:
        vtype = d.vtype
    else:
        pairs = [(p.attribute, str(p.type)) for p in prefs if not p.attribute.startswith("mirror:")]
        vtype = classify_violation(d.category, pairs, d.attribute)
    return StructuredSignal(
        category=d.category,
        attribute=d.attribute,
        violated_stated_preference=vtype in VIOLATION_TYPES_STATED,
        violation_type=vtype,
        confidence=d.confidence,
        explanation=explain(d.category, d.attribute, vtype, prefs),
        evidence=d.evidence[:300],
    )


class DemoProvider(LLMProvider):
    name = "demo"
    demo = True

    def structure_rejection(
        self,
        note: str,
        client_preferences: list[PreferenceIn],
        correction: str | None = None,
    ) -> StructuredFeedback:
        drafts = _CURATED.get(_norm(note)) or _keyword_drafts(note)
        return StructuredFeedback(signals=[_to_signal(d, client_preferences) for d in drafts])
