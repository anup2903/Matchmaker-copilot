"""Profile checker — pure, deterministic RED / AMBER / GREEN.

No database, no LLM. Hard blockers (RED) only ever come from a stored dealbreaker meeting a *known*
candidate attribute. Every reason carries a `source` and `evidence` so a matchmaker can see why.

    RED    a known candidate attribute violates a client dealbreaker
    AMBER  no hard blocker, but >=1 material warning:
             - strong-preference conflict
             - >=2 recent rejections citing something this candidate also has
             - match with a matchmaker-confirmed soft signal
             - unresolved stated-vs-observed pattern (Preference Mirror suggestion)
             - a dealbreaker that cannot be verified because the candidate attribute is unknown
    GREEN  neither of the above (positive matches and minor notes can still be shown)

No compatibility percentage is produced anywhere.
"""

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Literal

from app.core.geo import LONG_DISTANCE_KM, distance_km, same_city
from app.core.preferences import CATEGORY_PHRASES, describe_preference
from app.services.domain import (
    RECENT_DAYS,
    CandidateIn,
    CheckResult,
    ClientIn,
    MirrorSignalIn,
    PreferenceIn,
    Reason,
    SignalIn,
    as_utc,
)
from app.services.preference_mirror import MIRROR_RULES

MIN_REPEATED_REJECTIONS = 2  # >=2 triggers a warning; 3 is the primary demo

Outcome = Literal["violated", "satisfied", "unknown", "n/a"]
_EXCLUDED_CATEGORIES = frozenset({"other", "unclear"})
_EXCLUDED_VIOLATIONS = frozenset({"not_a_preference_violation", "unclear"})

_TYPE_WORD = {"dealbreaker": "dealbreaker", "strong": "strong preference", "soft": "soft preference"}


# ---------- per-preference evaluators: (outcome, candidate-side fact) ----------


def _eval_smoking(pref: PreferenceIn, c: CandidateIn, client: ClientIn) -> tuple[Outcome, str]:
    if pref.value.get("allowed", True):
        return "n/a", ""
    if c.smokes is None:
        return "unknown", "smoking status not recorded"
    return ("violated", "candidate smokes") if c.smokes else ("satisfied", "candidate does not smoke")


def _eval_drinking(pref: PreferenceIn, c: CandidateIn, client: ClientIn) -> tuple[Outcome, str]:
    if pref.value.get("allowed", True):
        return "n/a", ""
    if c.drinks is None:
        return "unknown", "drinking status not recorded"
    return ("violated", "candidate drinks") if c.drinks else ("satisfied", "candidate does not drink")


def _eval_children(pref: PreferenceIn, c: CandidateIn, client: ClientIn) -> tuple[Outcome, str]:
    client_wants = bool(pref.value.get("wants_children", True))
    if c.wants_children is None:
        return "unknown", "children plans not recorded"
    fact = "candidate wants children" if c.wants_children else "candidate does not want children"
    return ("satisfied" if c.wants_children == client_wants else "violated"), fact


def _eval_location(pref: PreferenceIn, c: CandidateIn, client: ClientIn) -> tuple[Outcome, str]:
    mode = pref.value.get("mode", "same_city")
    if mode == "max_distance_km":
        d = distance_km(client.location, c.location)
        if d is None:
            return "unknown", "distance could not be determined"
        if d <= float(pref.value.get("max_km", 0)):
            return "satisfied", f"candidate is ~{d:.0f} km away"
        fact = f"candidate is ~{d:.0f} km away ({c.location})"
    else:
        sc = same_city(client.location, c.location)
        if sc is None:
            return "unknown", "candidate location not recorded"
        if sc:
            return "satisfied", f"candidate lives in {c.location}"
        fact = f"candidate lives in {c.location}"
    # Different city / too far: relocation willingness decides whether this is a real conflict.
    if c.willing_to_relocate is True:
        return "satisfied", f"{fact}, but is willing to relocate"
    if c.willing_to_relocate is None:
        return ("unknown", f"{fact}; willingness to relocate not recorded") if pref.type == "dealbreaker" else (
            "violated",
            f"{fact}; willingness to relocate not recorded",
        )
    return "violated", f"{fact} and is not willing to relocate"


def _eval_age(pref: PreferenceIn, c: CandidateIn, client: ClientIn) -> tuple[Outcome, str]:
    if c.age is None:
        return "unknown", "age not recorded"
    lo, hi = pref.value.get("min"), pref.value.get("max")
    if (lo is not None and c.age < lo) or (hi is not None and c.age > hi):
        return "violated", f"candidate is {c.age}"
    return "satisfied", f"candidate is {c.age}"


def _eval_lifestyle(pref: PreferenceIn, c: CandidateIn, client: ClientIn) -> tuple[Outcome, str]:
    wanted = [str(t).lower() for t in pref.value.get("tags", [])]
    have = c.lifestyle_tags
    if not wanted:
        return "n/a", ""
    if not have:
        return "unknown", "lifestyle details not recorded"
    shared = [t for t in wanted if t in have]
    if shared:
        return "satisfied", f"shared interests: {', '.join(shared)}"
    return "violated", f"no shared lifestyle tags (candidate: {', '.join(have)})"


_EVALUATORS = {
    "smoking": _eval_smoking,
    "drinking": _eval_drinking,
    "children": _eval_children,
    "location": _eval_location,
    "age": _eval_age,
    "similar_lifestyle": _eval_lifestyle,
}

_MESSAGES = {
    # attribute -> (violated, satisfied, unknown) message templates
    "smoking": ("Candidate smokes.", "Candidate does not smoke.", "Candidate's smoking status is unknown."),
    "drinking": ("Candidate drinks.", "Candidate does not drink.", "Candidate's drinking status is unknown."),
    "children": (
        "Candidate's children plans conflict with the client's.",
        "Children plans align.",
        "Candidate's children plans are unknown.",
    ),
    "location": (
        "Candidate's location conflicts with the client's location preference.",
        "Location works for the client.",
        "Candidate's location / relocation status is unknown.",
    ),
    "age": ("Candidate is outside the client's age range.", "Candidate is within the client's age range.",
            "Candidate's age is unknown."),
    "similar_lifestyle": (
        "No overlap with the client's stated lifestyle interests.",
        "Lifestyle interests overlap.",
        "Candidate's lifestyle details are unknown.",
    ),
}


def _evaluate_preferences(
    prefs: list[PreferenceIn], client: ClientIn, candidate: CandidateIn, out: CheckResult
) -> None:
    for pref in prefs:
        evaluator = _EVALUATORS.get(pref.attribute)
        if evaluator is None:
            continue  # descriptive-only preference (e.g. intellectual_compatibility): handled by the Mirror
        outcome, fact = evaluator(pref, candidate, client)
        if outcome == "n/a":
            continue
        label = describe_preference(pref.attribute, pref.value)
        source = "dealbreaker" if pref.type == "dealbreaker" else "stated_preference"
        evidence = f"Client {_TYPE_WORD[pref.type]}: “{label}”; {fact}"
        violated_msg, satisfied_msg, unknown_msg = _MESSAGES[pref.attribute]
        code = f"{pref.attribute}:{outcome}"

        if outcome == "violated":
            reason = Reason(code, violated_msg, source, evidence)
            if pref.type == "dealbreaker":
                out.blocking_reasons.append(reason)
            elif pref.type == "strong":
                out.warnings.append(reason)
            else:  # soft + a single weak mismatch: shown, but not material
                out.notes.append(Reason(code, f"Minor mismatch: {violated_msg}", source, evidence))
        elif outcome == "satisfied":
            out.positive_signals.append(Reason(code, satisfied_msg, source, evidence))
        elif outcome == "unknown":
            reason = Reason(code, unknown_msg, source, f"Client {_TYPE_WORD[pref.type]}: “{label}”; {fact}")
            if pref.type == "dealbreaker":
                # we cannot confirm a dealbreaker is clear -> a human should verify before sharing
                out.warnings.append(
                    Reason(code, f"{unknown_msg} Verify before sharing (client dealbreaker).", source, reason.evidence)
                )
            elif pref.type == "strong":
                out.notes.append(reason)


# ---------- repeated rejection history ----------


def _candidate_pattern(category: str, signals: list[SignalIn], c: CandidateIn, client: ClientIn) -> str | None:
    """If this candidate has what past rejections in `category` keep citing, say what."""
    text = " ".join(f"{s.attribute} {s.evidence}" for s in signals).lower()
    if category == "location_distance":
        d = distance_km(client.location, c.location)
        if d is not None and d > LONG_DISTANCE_KM:
            return f"Candidate is ~{d:.0f} km from the client ({c.location})"
        return None
    if category == "smoking_alcohol":
        asks_smoke, asks_drink = "smok" in text, ("drink" in text or "alcohol" in text)
        if c.smokes and (asks_smoke or not asks_drink):
            return "Candidate smokes"
        if c.drinks and (asks_drink or not asks_smoke):
            return "Candidate drinks"
        return None
    if category == "children_family_plans":
        return "Candidate does not want children" if c.wants_children is False else None
    if category == "career_education":
        # college/pedigree patterns are surfaced through the Preference Mirror instead
        if any(k in text for k in ("college", "pedigree", "universit", "degree")):
            return None
        return f"Candidate is early in their career ({c.career or 'role not recorded'})" if c.career_level == "early" else None
    return None  # no candidate attribute to compare for the remaining categories


def _repeated_rejections(
    signals: list[SignalIn], client: ClientIn, candidate: CandidateIn, now: datetime, out: CheckResult
) -> None:
    cutoff = now - timedelta(days=RECENT_DAYS)
    by_category: dict[str, list[SignalIn]] = defaultdict(list)
    for s in signals:
        created = as_utc(s.created_at)
        if s.category in _EXCLUDED_CATEGORIES or s.violation_type in _EXCLUDED_VIOLATIONS:
            continue
        if created is not None and created < cutoff:
            continue
        by_category[s.category].append(s)

    for category, sigs in by_category.items():
        feedback_ids = list(dict.fromkeys(s.feedback_id for s in sigs))  # one note = one rejection
        if len(feedback_ids) < MIN_REPEATED_REJECTIONS:
            continue
        detail = _candidate_pattern(category, sigs, candidate, client)
        if not detail:
            continue
        quotes = " · ".join(f"“{s.evidence}”" for s in sigs[:3])
        phrase = CATEGORY_PHRASES.get(category, category.replace("_", " "))
        out.warnings.append(
            Reason(
                code=f"repeated:{category}",
                message=f"Client rejected {len(feedback_ids)} recent profiles citing {phrase}.",
                source="past_rejection",
                evidence=f"{quotes} — {detail}",
                refs=tuple(feedback_ids),
            )
        )


# ---------- Preference Mirror interplay ----------


def _mirror_warnings(
    mirror_signals: list[MirrorSignalIn], client: ClientIn, candidate: CandidateIn, out: CheckResult
) -> None:
    # confirmed signals first so the card surfaced to the UI is the human-confirmed one when both apply
    for ms in sorted(mirror_signals, key=lambda m: m.status != "confirmed"):
        rule = MIRROR_RULES.get(ms.rule_key)
        if rule is None or ms.status not in ("confirmed", "suggested"):
            continue
        detail = rule.candidate_trait(candidate, client.location)
        if not detail:
            continue
        if out.mirror_signal_id is None:
            out.mirror_signal_id = ms.id
        if ms.status == "confirmed":
            when = as_utc(ms.confirmed_at)
            stamp = f" on {when:%d %b %Y}" if when else ""
            out.warnings.append(
                Reason(
                    code=f"mirror_confirmed:{ms.rule_key}",
                    message=f"Matches a soft signal the matchmaker confirmed: {rule.trait_phrase}.",
                    source="confirmed_signal",
                    evidence=f"Confirmed{stamp} from {ms.supporting_count} rejections — {ms.possible_pattern} — {detail}",
                )
            )
        else:
            already_covered = any(w.code == f"repeated:{cat}" for w in out.warnings for cat in rule.base_categories)
            if already_covered:
                continue
            out.warnings.append(
                Reason(
                    code=f"mirror_suggested:{ms.rule_key}",
                    message=(
                        f"Possible stated-vs-observed pattern worth a look: {rule.trait_phrase} "
                        "(suggestion, not yet confirmed)."
                    ),
                    source="observed_pattern",
                    evidence=f"Preference Mirror, {ms.confidence} confidence — {ms.possible_pattern} — {detail}",
                )
            )


# ---------- entry point ----------


def check_profile(
    client: ClientIn,
    preferences: list[PreferenceIn],
    candidate: CandidateIn,
    rejection_signals: list[SignalIn],
    mirror_signals: list[MirrorSignalIn] | None = None,
    now: datetime | None = None,
) -> CheckResult:
    now = now or datetime.now(UTC)
    out = CheckResult(status="GREEN", summary="")

    # Matchmaker-confirmed "mirror:*" soft signals are applied through the mirror rules below, not here.
    stated = [p for p in preferences if not p.attribute.startswith("mirror:")]
    _evaluate_preferences(stated, client, candidate, out)
    _repeated_rejections(rejection_signals, client, candidate, now, out)
    _mirror_warnings(mirror_signals or [], client, candidate, out)

    if out.blocking_reasons:
        n = len(out.blocking_reasons)
        out.status = "RED"
        out.summary = f"Blocked by {n} dealbreaker{'s' if n != 1 else ''}"
    elif out.warnings:
        n = len(out.warnings)
        out.status = "AMBER"
        out.summary = f"{n} item{'s' if n != 1 else ''} to review before sharing"
    else:
        out.status = "GREEN"
        n = len(out.positive_signals)
        out.summary = (
            f"No blockers or warnings; {n} positive match{'es' if n != 1 else ''}"
            if n
            else "No blockers or warnings found in the stored data"
        )
    return out
