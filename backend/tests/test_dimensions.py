"""Observed-dimension tagging and the optional LLM phrasing of Mirror cards."""

from datetime import UTC, datetime, timedelta

import pytest

from app.core.preferences import FeedbackCategory, ObservedDimension, infer_dimension
from app.schemas.feedback import StructuredSignal
from app.services.domain import AcceptedIn, CandidateIn, FeedbackIn, PreferenceIn, SignalIn
from app.services.llm.provider import LLMProvider
from app.services.mirror_phrasing import is_acceptable, make_phraser, phrase_draft
from app.services.preference_mirror import compute_mirror_cards

NOW = datetime(2026, 6, 1, tzinfo=UTC)


# ---- dimension inference (the deterministic fallback used by demo + seed) ------------------------------------


@pytest.mark.parametrize(
    "category,attribute,evidence,expected",
    [
        (FeedbackCategory.career_education, "college pedigree", "his college wasn't strong", ObservedDimension.education_prestige),
        (FeedbackCategory.career_education, "career trajectory", "not very driven", ObservedDimension.career_ambition),
        (FeedbackCategory.intellectual_fit, "intellectual compatibility", "no spark", ObservedDimension.intellectual_depth),
        (FeedbackCategory.smoking_alcohol, "smoking", "she smokes", ObservedDimension.smoking),
        (FeedbackCategory.smoking_alcohol, "drinking", "drinks a lot", ObservedDimension.drinking),
        (FeedbackCategory.location_distance, "distance", "too far", ObservedDimension.physical_distance),
        (FeedbackCategory.values_lifestyle, "living arrangements", "wants to live with parents", ObservedDimension.family_setup),
        (FeedbackCategory.values_lifestyle, "lifestyle", "always at parties", ObservedDimension.lifestyle_social),
        (FeedbackCategory.values_lifestyle, "lifestyle", "daily routines differ", ObservedDimension.values_lifestyle),
        (FeedbackCategory.unclear, "overall fit", "just didn't feel it", ObservedDimension.unclear),
    ],
)
def test_infer_dimension(category, attribute, evidence, expected):
    assert infer_dimension(category, attribute, evidence) == expected


def test_signal_autofills_dimension_when_model_omits_it():
    s = StructuredSignal(
        category="career_education",
        attribute="college pedigree",
        violated_stated_preference=False,
        violation_type="new_signal",
        confidence="medium",
        explanation="x",
        evidence="his college background was weak",
    )
    assert s.observed_dimension == ObservedDimension.education_prestige


def test_signal_keeps_dimension_the_model_supplies():
    s = StructuredSignal(
        category="career_education",
        attribute="career",
        observed_dimension="financial_stability",
        violated_stated_preference=False,
        violation_type="new_signal",
        confidence="medium",
        explanation="x",
        evidence="not financially settled",
    )
    assert s.observed_dimension == ObservedDimension.financial_stability


# ---- dimension-driven Mirror matching ------------------------------------------------------------------------


def _fb(n, dim, *, days=10):
    when = NOW - timedelta(days=days + n)
    return FeedbackIn(
        id=f"f{n}",
        created_at=when,
        signals=(SignalIn(f"f{n}", "career_education", "x", f"evidence {n}", "new_signal", "high", when, observed_dimension=dim),),
    )


def test_proxy_counting_uses_dimensions_not_keywords():
    # intellectual_pedigree: base dimension intellectual_depth, proxy education_prestige
    prefs = [PreferenceIn("intellectual_compatibility", {"importance": "high"}, "strong")]
    feedback = [
        FeedbackIn("a", NOW - timedelta(days=5), (SignalIn("a", "intellectual_fit", "fit", "no spark", "stated_preference", "high", NOW, observed_dimension="intellectual_depth"),)),
        FeedbackIn("b", NOW - timedelta(days=6), (SignalIn("b", "career_education", "college", "weak college", "new_signal", "high", NOW, observed_dimension="education_prestige"),)),
        FeedbackIn("c", NOW - timedelta(days=7), (SignalIn("c", "career_education", "college", "poor university", "new_signal", "high", NOW, observed_dimension="education_prestige"),)),
    ]
    accepted = [AcceptedIn("d1", CandidateIn(id="x", name="X", location="Mumbai", education_tier="standard"), NOW)]
    (card,) = compute_mirror_cards(prefs, feedback, accepted, "Mumbai", NOW)
    assert card.rule_key == "intellectual_pedigree"
    assert "2 mention college pedigree" in card.observed_summary
    assert card.possible_pattern.startswith("Education prestige may be acting as a proxy")


# ---- LLM phrasing validation ---------------------------------------------------------------------------------


class _DraftStub:
    mixed_evidence = False
    possible_pattern = "Education prestige may be acting as a proxy for perceived intellectual compatibility."
    stated_text = "Intellectual compatibility is important."
    observed_summary = "3 recent rejections mention intellectual fit; 2 mention college pedigree."


def test_is_acceptable_rules():
    d = _DraftStub()
    assert is_acceptable("Education prestige may be acting as a proxy for intellectual fit.", d)
    assert not is_acceptable("Education prestige is DEFINITELY what they want.", d)  # forbidden + no hedge
    assert not is_acceptable("They rejected 3 people for college reasons, so they may care.", d)  # has a number
    assert not is_acceptable("Education prestige is the real driver here.", d)  # no hedge word
    assert not is_acceptable("", d)


class _Phraser(LLMProvider):
    demo = False

    def __init__(self, reply):
        self._reply = reply

    def structure_rejection(self, note, client_preferences, correction=None):  # pragma: no cover
        raise NotImplementedError

    def phrase_pattern(self, instruction):
        return self._reply


def test_phrase_draft_uses_valid_llm_sentence():
    d = _DraftStub()
    good = "Prestige of education could be standing in for how this client reads intellectual connection."
    assert phrase_draft(d, _Phraser(good)) == good


def test_phrase_draft_falls_back_on_invalid_or_none():
    d = _DraftStub()
    assert phrase_draft(d, _Phraser("They DEFINITELY only want IIT grads.")) == d.possible_pattern  # invalid
    assert phrase_draft(d, _Phraser(None)) == d.possible_pattern  # provider declined
    assert phrase_draft(d, _Phraser("boom")) == d.possible_pattern  # no hedge


def test_demo_provider_makes_templates_only():
    from app.services.llm.demo import DemoProvider

    phraser = make_phraser(DemoProvider())
    assert phraser is not None
    d = _DraftStub()
    assert phraser(d) == d.possible_pattern


def test_make_phraser_none_when_no_provider():
    assert make_phraser(None) is None
