"""Feedback structuring: scenarios, Pydantic validation, retry behaviour, guardrails, provider adapter."""

import json

import httpx
import pytest
from pydantic import ValidationError

from app.schemas.feedback import StructuredFeedback, StructuredSignal
from app.services.domain import PreferenceIn
from app.services.feedback_structurer import structure_feedback, verify_evidence
from app.services.llm.demo import SAMPLE_NOTES, DemoProvider
from app.services.llm.openai_compat import OpenAICompatibleProvider, parse_model_output
from app.services.llm.provider import InvalidModelOutputError, LLMProvider, LLMUnavailableError

ANANYA_PREFS = [
    PreferenceIn("intellectual_compatibility", {"importance": "high"}, "strong"),
    PreferenceIn("smoking", {"allowed": False}, "dealbreaker"),
    PreferenceIn("open_to_relocation", {"open": True}, "soft"),
    PreferenceIn("similar_lifestyle", {"tags": ["fitness"]}, "strong"),
]
NO_PREFS: list[PreferenceIn] = []


def note(sample_id: str) -> str:
    return next(s["note"] for s in SAMPLE_NOTES if s["id"] == sample_id)


def run(text, prefs=ANANYA_PREFS, provider=None):
    return structure_feedback(text, prefs, provider or DemoProvider())


# ---- the five required scenarios (via the deterministic demo extractor) -------------------------------------


def test_explicit_preference_violation_matches_spec_example():
    res = run(note("intellectual-and-distance"))
    intellectual = next(s for s in res.feedback.signals if s.category.value == "intellectual_fit")
    assert intellectual.attribute == "intellectual compatibility"
    assert intellectual.violated_stated_preference is True
    assert intellectual.violation_type.value == "stated_preference"
    assert intellectual.confidence.value == "high"
    assert intellectual.evidence == "didn’t feel we’d connect intellectually"
    assert "intellectual" in intellectual.explanation.lower()


def test_dealbreaker_type_comes_from_stored_preferences():
    res = run(note("smoking"))
    sig = res.feedback.signals[0]
    assert sig.category.value == "smoking_alcohol"
    assert sig.violation_type.value == "dealbreaker"
    assert sig.violated_stated_preference is True
    # same note, client with no smoking preference -> a new signal, not a violation
    other = run(note("smoking"), NO_PREFS).feedback.signals[0]
    assert other.violation_type.value == "new_signal" and other.violated_stated_preference is False


def test_new_signal_when_no_stated_preference_covers_it():
    sig = run(note("new-signal")).feedback.signals[0]
    assert sig.category.value == "communication_personality"
    assert sig.violation_type.value == "new_signal"
    assert sig.violated_stated_preference is False


def test_multiple_reasons_return_an_array_not_a_blend():
    res = run(note("multiple-reasons"))
    categories = [s.category.value for s in res.feedback.signals]
    assert len(res.feedback.signals) == 3
    assert set(categories) == {"location_distance", "age", "children_family_plans"}


def test_ambiguous_note_is_unclear_with_low_confidence():
    sig = run(note("ambiguous")).feedback.signals[0]
    assert sig.category.value == "unclear"
    assert sig.violation_type.value == "unclear"
    assert sig.confidence.value == "low"
    assert sig.violated_stated_preference is False


def test_unrelated_note_is_not_a_preference_violation():
    sig = run(note("unrelated")).feedback.signals[0]
    assert sig.violation_type.value == "not_a_preference_violation"
    assert sig.violated_stated_preference is False


def test_demo_mode_flag_and_notice():
    res = run(note("smoking"))
    assert res.demo_mode is True and res.provider == "demo" and res.notice


def test_keyword_extractor_handles_unseen_text_with_verbatim_evidence():
    text = "Lovely evening but I could not get past how far away they live."
    res = run(text)
    assert res.feedback.signals[0].category.value == "location_distance"
    assert res.feedback.signals[0].evidence in text


def test_every_sample_note_produces_valid_verbatim_signals():
    for sample in SAMPLE_NOTES:
        res = run(sample["note"])
        verify_evidence(res.feedback, sample["note"])


# ---- Pydantic contract ---------------------------------------------------------------------------------------


def _signal(**kw):
    base = dict(
        category="location_distance",
        attribute="distance",
        violated_stated_preference=True,
        violation_type="stated_preference",
        confidence="high",
        explanation="Because.",
        evidence="too far",
    )
    base.update(kw)
    return base


def test_contract_rejects_unknown_category_and_extra_fields():
    with pytest.raises(ValidationError):
        StructuredSignal(**_signal(category="astrology"))
    with pytest.raises(ValidationError):
        StructuredSignal(**_signal(sneaky="x"))


def test_contract_rejects_inconsistent_violation_flag():
    with pytest.raises(ValidationError):
        StructuredSignal(**_signal(violated_stated_preference=False, violation_type="dealbreaker"))
    with pytest.raises(ValidationError):
        StructuredSignal(**_signal(violated_stated_preference=True, violation_type="new_signal"))


def test_parse_model_output_tolerates_code_fences_but_not_garbage():
    payload = {"signals": [_signal()]}
    assert parse_model_output("```json\n" + json.dumps(payload) + "\n```").signals[0].attribute == "distance"
    with pytest.raises(InvalidModelOutputError):
        parse_model_output("not json at all")
    with pytest.raises(InvalidModelOutputError):
        parse_model_output(json.dumps({"signals": []}))


# ---- retry / error behaviour with a scripted provider --------------------------------------------------------


class ScriptedProvider(LLMProvider):
    name = "llm"
    demo = False

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.corrections: list[str | None] = []

    def structure_rejection(self, note, client_preferences, correction=None):
        self.corrections.append(correction)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _feedback(evidence="too far", **kw):
    return StructuredFeedback(signals=[StructuredSignal(**_signal(evidence=evidence, **kw))])


def test_malformed_output_is_retried_once_with_corrective_instruction():
    provider = ScriptedProvider(InvalidModelOutputError("reply was not valid JSON"), _feedback())
    res = structure_feedback("Honestly it was too far for me.", ANANYA_PREFS, provider)
    assert res.demo_mode is False and res.provider == "llm"
    assert provider.corrections[0] is None
    assert "could not be accepted" in provider.corrections[1]


def test_second_malformed_output_becomes_a_clean_error():
    provider = ScriptedProvider(InvalidModelOutputError("bad"), InvalidModelOutputError("still bad"))
    with pytest.raises(InvalidModelOutputError):
        structure_feedback("too far", ANANYA_PREFS, provider)
    assert len(provider.corrections) == 2  # exactly one retry


def test_invented_evidence_is_rejected_and_retried():
    provider = ScriptedProvider(_feedback(evidence="this quote is not in the note"), _feedback(evidence="too far"))
    res = structure_feedback("It was just too far.", ANANYA_PREFS, provider)
    assert res.feedback.signals[0].evidence == "too far"
    assert "verbatim" in provider.corrections[1]


def test_timeout_is_retried_once_then_surfaces_as_unavailable():
    provider = ScriptedProvider(LLMUnavailableError("timeout"), _feedback())
    assert structure_feedback("too far", ANANYA_PREFS, provider).feedback.signals
    provider = ScriptedProvider(LLMUnavailableError("timeout"), LLMUnavailableError("timeout"))
    with pytest.raises(LLMUnavailableError):
        structure_feedback("too far", ANANYA_PREFS, provider)


def test_guardrail_downgrades_llm_claim_without_a_matching_stored_preference():
    # model claims "stated preference violation" for distance, but this client has no location preference
    provider = ScriptedProvider(_feedback(violation_type="stated_preference", violated_stated_preference=True))
    sig = structure_feedback("too far", ANANYA_PREFS, provider).feedback.signals[0]
    assert sig.violation_type.value == "new_signal"
    assert sig.violated_stated_preference is False


def test_guardrail_never_lets_model_invent_a_dealbreaker():
    prefs = [PreferenceIn("location", {"mode": "same_city"}, "strong")]
    provider = ScriptedProvider(_feedback(violation_type="dealbreaker", violated_stated_preference=True))
    sig = structure_feedback("too far", prefs, provider).feedback.signals[0]
    assert sig.violation_type.value == "stated_preference"  # strength comes from stored data, not the model


# ---- OpenAI-compatible adapter (HTTP mocked) -----------------------------------------------------------------


def _provider(handler):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return OpenAICompatibleProvider(api_key="sk-test", model="any-model", base_url="https://llm.example/v1", client=client)


def _ok(content):
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def test_adapter_sends_schema_and_never_leaks_key_into_body():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        seen["auth"] = request.headers["authorization"]
        return _ok(json.dumps({"signals": [_signal()]}))

    out = _provider(handler).structure_rejection("too far", ANANYA_PREFS)
    assert out.signals[0].category.value == "location_distance"
    assert seen["body"]["model"] == "any-model"
    assert seen["body"]["response_format"]["type"] == "json_schema"
    assert "sk-test" not in json.dumps(seen["body"]) and seen["auth"] == "Bearer sk-test"
    user_msg = seen["body"]["messages"][1]["content"]
    assert "Rejection note" in user_msg and "Dealbreakers" in user_msg and "Non-smoker" in user_msg


def test_adapter_falls_back_to_json_mode_when_schema_format_unsupported():
    calls = []

    def handler(request):
        fmt = json.loads(request.content)["response_format"]["type"]
        calls.append(fmt)
        return httpx.Response(400, json={"error": "unsupported"}) if fmt == "json_schema" else _ok(
            json.dumps({"signals": [_signal()]})
        )

    _provider(handler).structure_rejection("too far", ANANYA_PREFS)
    assert calls == ["json_schema", "json_object"]


def test_adapter_maps_timeouts_and_auth_errors_to_unavailable():
    def timeout(request):
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(LLMUnavailableError):
        _provider(timeout).structure_rejection("too far", ANANYA_PREFS)
    with pytest.raises(LLMUnavailableError):
        _provider(lambda r: httpx.Response(401, json={})).structure_rejection("too far", ANANYA_PREFS)


def test_adapter_rejects_malformed_model_json():
    with pytest.raises(InvalidModelOutputError):
        _provider(lambda r: _ok('{"signals": [{"category": "nope"}]}')).structure_rejection("x", ANANYA_PREFS)


# ---- robustness to sloppy-but-sensible model output (found with a real model) ---------------------------------


def test_missing_attribute_is_derived_not_rejected():
    payload = {"signals": [{
        "category": "smoking_alcohol", "observed_dimension": "smoking", "violation_type": "dealbreaker",
        "violated_stated_preference": True, "confidence": "high",
        "evidence": "she vapes occasionally", "explanation": "x"}]}
    out = parse_model_output(json.dumps(payload))
    assert out.signals[0].attribute == "smoking"


def test_blank_attribute_and_missing_dimension_both_filled():
    s = StructuredSignal(**_signal(attribute="  ", observed_dimension=None, category="location_distance"))
    assert s.attribute == "distance" and s.observed_dimension.value == "physical_distance"


def test_stray_keys_from_the_model_are_dropped_not_fatal():
    payload = {"signals": [{**_signal(), "confidence_score": 0.93, "notes": "extra"}]}
    assert parse_model_output(json.dumps(payload)).signals[0].category.value == "location_distance"


# ---- hedged wording caps confidence (the model alone tends to over-claim) ---------------------------------------


def _one(evidence, confidence="high", **kw):
    return StructuredFeedback(signals=[StructuredSignal(**_signal(evidence=evidence, confidence=confidence, **kw))])


def test_strong_hedge_caps_confidence_to_low():
    note = "Hmm not sure, no chemistry I guess."
    out = structure_feedback(note, NO_PREFS, ScriptedProvider(_one("no chemistry", category="attraction_first_impression",
                             violation_type="new_signal", violated_stated_preference=False)))
    assert out.feedback.signals[0].confidence.value == "low"


def test_soft_hedge_caps_confidence_to_medium():
    note = "He seemed ok but kinda boring and that's why we passed."
    out = structure_feedback(note, NO_PREFS, ScriptedProvider(_one("kinda boring", category="communication_personality",
                             violation_type="new_signal", violated_stated_preference=False)))
    assert out.feedback.signals[0].confidence.value == "medium"


def test_hedge_in_another_clause_does_not_cap_a_confident_signal():
    # "maybe" belongs to the other clause; the evidence clause is explicit
    note = "Maybe it was timing, but she smokes and I need a non-smoker."
    out = structure_feedback(note, ANANYA_PREFS, ScriptedProvider(_one("she smokes and I need a non-smoker",
                             category="smoking_alcohol", attribute="smoking")))
    assert out.feedback.signals[0].confidence.value == "high"


def test_hedging_never_raises_confidence():
    note = "Maybe it was too far."
    out = structure_feedback(note, NO_PREFS, ScriptedProvider(_one("too far", confidence="low",
                             violation_type="new_signal", violated_stated_preference=False)))
    assert out.feedback.signals[0].confidence.value == "low"


def test_spec_example_stays_high_for_the_explicit_reason():
    sig = run(note("intellectual-and-distance")).feedback.signals[0]
    assert sig.confidence.value == "high"


# ---- every label comes from a fixed list: attribute is derived, never free text -----------------------------------


def test_attribute_is_always_derived_from_the_dimension_even_if_the_model_supplies_one():
    s = StructuredSignal(**_signal(attribute="some creative model wording", observed_dimension="education_prestige",
                                   category="career_education", violation_type="new_signal",
                                   violated_stated_preference=False))
    assert s.attribute == "college pedigree"


def test_same_idea_always_gets_the_same_attribute_label():
    wordings = ["his college", "poor alma mater", "education level"]
    labels = {StructuredSignal(**_signal(attribute=w, observed_dimension="education_prestige",
                                         category="career_education",
                                         violation_type="new_signal", violated_stated_preference=False)).attribute
              for w in wordings}
    assert labels == {"college pedigree"}


def test_schema_sent_to_the_model_does_not_ask_for_attribute():
    from app.services.llm.openai_compat import _llm_schema

    props = _llm_schema()["$defs"]["StructuredSignal"]["properties"]
    assert "attribute" not in props and "observed_dimension" in props and "category" in props


def test_timing_notes_get_the_timing_dimension():
    sig = run(note("unrelated")).feedback.signals[0]
    assert sig.observed_dimension.value == "timing_availability" and sig.attribute == "timing / availability"


def test_drinking_dimension_still_matches_a_drinking_preference_not_a_smoking_one():
    prefs = [PreferenceIn("smoking", {"allowed": False}, "soft")]  # smoking soft, no drinking preference
    provider = ScriptedProvider(_feedback(evidence="always out at parties", category="smoking_alcohol",
                                          observed_dimension="lifestyle_social", violation_type="new_signal",
                                          violated_stated_preference=False))
    sig = structure_feedback("He is always out at parties.", prefs, provider).feedback.signals[0]
    assert sig.attribute == "drinking and nightlife"
    assert sig.violation_type.value == "new_signal"  # a smoking preference must not be flagged by a drinking complaint
