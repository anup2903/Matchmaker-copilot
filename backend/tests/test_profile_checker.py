"""Pure profile-checker scenarios: no DB, no LLM."""

from datetime import UTC, datetime, timedelta

from app.services.domain import (
    CandidateIn,
    ClientIn,
    MirrorSignalIn,
    PreferenceIn,
    SignalIn,
)
from app.services.profile_checker import check_profile

NOW = datetime(2026, 6, 1, tzinfo=UTC)
CLIENT = ClientIn(id="c1", name="Ananya", location="Mumbai")


def pref(attribute, value, type_="dealbreaker"):
    return PreferenceIn(attribute=attribute, value=value, type=type_)


def candidate(**kw):
    base = dict(
        id="k1",
        name="Candidate",
        age=32,
        location="Mumbai",
        smokes=False,
        drinks=False,
        wants_children=True,
        willing_to_relocate=True,
        education="Some College",
        education_tier="prestigious",
        career="Manager",
        career_level="senior",
        values_lifestyle={"tags": ["travel"]},
    )
    base.update(kw)
    return CandidateIn(**base)


def rejection(n, category="location_distance", attribute="distance", evidence="too far", days=10):
    return SignalIn(
        feedback_id=f"fb{n}",
        category=category,
        attribute=attribute,
        evidence=f"{evidence} {n}",
        violation_type="new_signal",
        confidence="high",
        created_at=NOW - timedelta(days=days),
    )


def run(prefs, cand, signals=(), mirror=(), client=CLIENT):
    return check_profile(client, prefs, cand, list(signals), list(mirror), now=NOW)


# ---- RED -------------------------------------------------------------------------------------------------


def test_smoking_dealbreaker_is_red_with_source_and_evidence():
    res = run([pref("smoking", {"allowed": False})], candidate(smokes=True))
    assert res.status == "RED"
    reason = res.blocking_reasons[0]
    assert reason.source == "dealbreaker"
    assert "smokes" in reason.message.lower()
    assert "Non-smoker" in reason.evidence
    assert res.summary == "Blocked by 1 dealbreaker"


def test_children_dealbreaker_is_red():
    res = run([pref("children", {"wants_children": True})], candidate(wants_children=False))
    assert res.status == "RED"
    assert res.blocking_reasons[0].source == "dealbreaker"
    assert "Wants children" in res.blocking_reasons[0].evidence


def test_location_dealbreaker_is_red_only_when_candidate_will_not_relocate():
    prefs = [pref("location", {"mode": "same_city"})]
    far = candidate(location="Delhi", willing_to_relocate=False)
    assert run(prefs, far).status == "RED"
    # willing to relocate -> not a hard conflict
    assert run(prefs, candidate(location="Delhi", willing_to_relocate=True)).status == "GREEN"


def test_dealbreaker_beats_everything_else():
    prefs = [pref("smoking", {"allowed": False})]
    signals = [rejection(i) for i in range(3)]
    res = run(prefs, candidate(smokes=True, location="Delhi"), signals)
    assert res.status == "RED"


# ---- AMBER -----------------------------------------------------------------------------------------------


def test_repeated_long_distance_rejections_are_amber():
    signals = [rejection(i, evidence="too far") for i in range(3)]
    res = run([], candidate(location="Delhi"), signals)
    assert res.status == "AMBER"
    w = res.warnings[0]
    assert w.source == "past_rejection"
    assert "rejected 3 recent profiles citing long distance" in w.message
    assert "too far 0" in w.evidence
    assert len(w.refs) == 3


def test_two_rejections_is_the_minimum_and_one_is_not_enough():
    assert run([], candidate(location="Delhi"), [rejection(0), rejection(1)]).status == "AMBER"
    assert run([], candidate(location="Delhi"), [rejection(0)]).status == "GREEN"


def test_repeated_pattern_only_applies_when_candidate_actually_has_it():
    signals = [rejection(i) for i in range(3)]
    assert run([], candidate(location="Mumbai"), signals).status == "GREEN"  # same city: no pattern match


def test_old_rejections_do_not_count():
    signals = [rejection(i, days=400) for i in range(3)]
    assert run([], candidate(location="Delhi"), signals).status == "GREEN"


def test_one_note_with_two_signals_counts_once():
    s1 = rejection(0)
    s2 = SignalIn(**{**s1.__dict__, "evidence": "also far"})  # same feedback_id
    assert run([], candidate(location="Delhi"), [s1, s2]).status == "GREEN"


def test_confirmed_soft_signal_mismatch_is_amber():
    mirror = [
        MirrorSignalIn(
            id="m1",
            rule_key="intellectual_pedigree",
            status="confirmed",
            confidence="medium",
            possible_pattern="Education prestige may be acting as a proxy for intellectual compatibility.",
            supporting_count=3,
            confirmed_at=NOW,
        )
    ]
    res = run([], candidate(education_tier="standard", education="State College"), mirror=mirror)
    assert res.status == "AMBER"
    assert res.warnings[0].source == "confirmed_signal"
    assert res.mirror_signal_id == "m1"
    # a candidate without the trait is unaffected
    assert run([], candidate(education_tier="prestigious"), mirror=mirror).status == "GREEN"


def test_unconfirmed_mirror_suggestion_is_an_unresolved_inconsistency_warning():
    mirror = [
        MirrorSignalIn("m1", "intellectual_pedigree", "suggested", "medium", "Possible pattern.", supporting_count=3)
    ]
    res = run([], candidate(education_tier="standard"), mirror=mirror)
    assert res.status == "AMBER"
    assert res.warnings[0].source == "observed_pattern"
    assert "not yet confirmed" in res.warnings[0].message


def test_strong_preference_conflict_is_amber():
    prefs = [pref("drinking", {"allowed": False}, "strong")]
    res = run(prefs, candidate(drinks=True))
    assert res.status == "AMBER"
    assert res.warnings[0].source == "stated_preference"


def test_dealbreaker_with_unknown_candidate_attribute_needs_verification_not_red():
    res = run([pref("smoking", {"allowed": False})], candidate(smokes=None))
    assert res.status == "AMBER"
    assert "unknown" in res.warnings[0].message.lower()


# ---- GREEN -----------------------------------------------------------------------------------------------


def test_clean_candidate_is_green_with_positive_matches():
    prefs = [
        pref("smoking", {"allowed": False}),
        pref("children", {"wants_children": True}, "strong"),
        pref("similar_lifestyle", {"tags": ["travel", "fitness"]}, "strong"),
    ]
    res = run(prefs, candidate())
    assert res.status == "GREEN"
    assert not res.blocking_reasons and not res.warnings
    assert len(res.positive_signals) == 3
    assert all(p.evidence for p in res.positive_signals)


def test_weak_soft_mismatch_stays_green_with_a_note():
    res = run([pref("drinking", {"allowed": False}, "soft")], candidate(drinks=True))
    assert res.status == "GREEN"
    assert res.notes and "Minor mismatch" in res.notes[0].message


def test_no_compatibility_score_is_exposed():
    res = run([pref("smoking", {"allowed": False})], candidate())
    assert not hasattr(res, "score") and "%" not in res.summary


def test_every_red_and_amber_reason_has_source_and_evidence():
    prefs = [pref("smoking", {"allowed": False}), pref("drinking", {"allowed": False}, "strong")]
    res = run(prefs, candidate(smokes=True, drinks=True), [rejection(i) for i in range(3)])
    for r in res.blocking_reasons + res.warnings:
        assert r.source and r.evidence and r.message
