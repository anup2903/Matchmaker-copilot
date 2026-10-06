"""Preference Mirror engine — pure and deterministic.

"What the client says" vs "what their decisions suggest".

Pipeline (CLAUDE.md / BUILD_SPEC §12):
  A. aggregate saved feedback by client           (caller loads FeedbackIn rows)
  B. compare with the client's stated preferences (a rule only applies if its stated attribute exists)
  C. detect proxy patterns via a small hard-coded rule table (no ontology)
  D. evidence threshold: never a card from a single rejection
  E. confidence: High  = 4+ supporting rejections + >=1 similar accepted profile
                 Medium= 2-3 supporting rejections + >=1 similar accepted profile
                 Low   = 2+ supporting rejections, no similar accepted profile
  F. wording comes from templates over structured evidence — no LLM, nothing invented.

Everything here is advisory. Nothing in this module mutates a preference.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.core.geo import LONG_DISTANCE_KM, distance_km
from app.core.preferences import DIMENSION_CATEGORY, STRENGTH_WORDS, FeedbackCategory, infer_dimension
from app.services.domain import (
    RECENT_DAYS,
    AcceptedIn,
    CandidateIn,
    FeedbackIn,
    PreferenceIn,
    SignalIn,
    as_utc,
)

MIN_SUPPORTING_REJECTIONS = 2
# A dismissed pattern only comes back once it has this many more supporting rejections than when dismissed.
REAPPEAR_EXTRA_REJECTIONS = 2
# Language we never want in a card; asserted by tests.
FORBIDDEN_PHRASES = ("secretly", "is lying", "definitely", "really wants", "proves")

_IGNORED_CATEGORIES = frozenset({"other", "unclear"})
_IGNORED_VIOLATION_TYPES = frozenset({"not_a_preference_violation", "unclear"})

TraitFn = Callable[[CandidateIn, str | None], str | None]


@dataclass(frozen=True)
class MirrorRule:
    """One stated-preference vs observed-behaviour pattern, defined as DATA.

    Adding a new Preference Mirror pattern is adding an entry to MIRROR_RULES — a stated preference to
    compare against, the observed dimension(s) that form the base signal, optional proxy dimension(s), and
    phrasing templates. An optional `trait` makes a confirmed pattern actionable in Check Profile; without
    one the pattern is still shown and confirmable, just advisory (not auto-checked against candidates).
    """

    key: str
    stated_attribute: str  # client preference attribute that must exist for this rule to apply
    stated_template: str  # "{strength}" is replaced with important / somewhat important / ...
    observed_attribute: str
    base_dimensions: frozenset[str]  # ObservedDimension values that count as the base signal
    base_phrase: str
    proxy_dimensions: frozenset[str] = frozenset()
    proxy_phrase: str | None = None
    pattern_with_proxy: str = ""
    pattern_plain: str = ""
    trait_phrase: str = ""  # shown in profile-check warnings
    trait: TraitFn | None = field(default=None)

    @property
    def base_categories(self) -> frozenset[str]:
        """Feedback categories the base dimensions roll up to (used to de-dupe profile-check warnings)."""
        return frozenset(DIMENSION_CATEGORY[d].value for d in self.base_dimensions if d in DIMENSION_CATEGORY)

    def candidate_trait(self, candidate: CandidateIn, client_location: str | None) -> str | None:
        """Detail string if the candidate has the trait the rejections keep citing, else None."""
        return self.trait(candidate, client_location) if self.trait else None


# ---- candidate "trait" predicates: does this candidate have the thing the rejections keep citing? ----


def _trait_not_top_tier(c: CandidateIn, _loc: str | None) -> str | None:
    if c.education_tier == "standard":
        return f"Candidate's college ({c.education or 'not recorded'}) is not top-tier"
    return None


def _trait_long_distance(c: CandidateIn, client_location: str | None) -> str | None:
    d = distance_km(client_location, c.location)
    if d is not None and d > LONG_DISTANCE_KM:
        return f"Candidate is ~{d:.0f} km away ({c.location})"
    return None


def _trait_early_career(c: CandidateIn, _loc: str | None) -> str | None:
    if c.career_level == "early":
        return f"Candidate is early in their career ({c.career or 'role not recorded'})"
    return None


def _trait_lives_with_parents(c: CandidateIn, _loc: str | None) -> str | None:
    if (c.values_lifestyle or {}).get("family_setup") == "lives_with_parents":
        return "Candidate lives with / expects to live with parents"
    return None


def _trait_social_lifestyle(c: CandidateIn, _loc: str | None) -> str | None:
    if c.drinks is True or (c.values_lifestyle or {}).get("social_style") == "nightlife":
        return "Candidate has a social / nightlife-oriented lifestyle"
    return None


MIRROR_RULES: dict[str, MirrorRule] = {
    r.key: r
    for r in (
        MirrorRule(
            key="intellectual_pedigree",
            stated_attribute="intellectual_compatibility",
            stated_template="Intellectual compatibility is {strength}.",
            observed_attribute="education pedigree",
            base_dimensions=frozenset({"intellectual_depth"}),
            base_phrase="intellectual fit",
            proxy_dimensions=frozenset({"education_prestige"}),
            proxy_phrase="college pedigree",
            pattern_with_proxy=(
                "Education prestige may be acting as a proxy for perceived intellectual compatibility."
            ),
            pattern_plain=(
                "Recent rejections repeatedly cite intellectual fit, which may mean this client judges it "
                "differently from how it is currently recorded."
            ),
            trait_phrase="college is not top-tier",
            trait=_trait_not_top_tier,
        ),
        MirrorRule(
            key="relocation_distance",
            stated_attribute="open_to_relocation",
            stated_template="Open to relocation: yes.",
            observed_attribute="distance",
            base_dimensions=frozenset({"physical_distance", "relocation"}),
            base_phrase="distance",
            pattern_plain=(
                "Distance appears to be a practical constraint in this client's decisions, even though they "
                "describe themselves as open to relocation."
            ),
            pattern_with_proxy=(
                "Distance appears to be a practical constraint in this client's decisions, even though they "
                "describe themselves as open to relocation."
            ),
            trait_phrase="long-distance candidate",
            trait=_trait_long_distance,
        ),
        MirrorRule(
            key="ambition_trajectory",
            stated_attribute="ambition",
            stated_template="Ambition is {strength}.",
            observed_attribute="career trajectory",
            base_dimensions=frozenset({"career_ambition", "financial_stability"}),
            base_phrase="career trajectory",
            proxy_dimensions=frozenset({"education_prestige"}),
            proxy_phrase="education pedigree",
            pattern_with_proxy=(
                "Career stage and education pedigree may be acting as proxies for how this client reads ambition."
            ),
            pattern_plain=(
                "Recent rejections repeatedly cite career trajectory, which may be how this client "
                "interprets ambition."
            ),
            trait_phrase="early-career candidate",
            trait=_trait_early_career,
        ),
        MirrorRule(
            key="family_expectations",
            stated_attribute="family_compatibility",
            stated_template="Family compatibility is {strength}.",
            observed_attribute="family setup and location expectations",
            base_dimensions=frozenset({"family_background"}),
            base_phrase="family background",
            proxy_dimensions=frozenset({"family_setup"}),
            proxy_phrase="living arrangements around parents",
            pattern_with_proxy=(
                "Expectations about living arrangements and proximity to family may be shaping how this "
                "client judges family compatibility."
            ),
            pattern_plain=(
                "Recent rejections repeatedly cite family background, which may point to specific family "
                "setup expectations that are not yet recorded."
            ),
            trait_phrase="family setup differs (lives with parents)",
            trait=_trait_lives_with_parents,
        ),
        MirrorRule(
            key="lifestyle_social_habits",
            stated_attribute="similar_lifestyle",
            stated_template="Similar lifestyle is {strength}.",
            observed_attribute="social habits",
            base_dimensions=frozenset({"values_lifestyle", "lifestyle_health"}),
            base_phrase="lifestyle differences",
            proxy_dimensions=frozenset({"lifestyle_social", "drinking"}),
            proxy_phrase="social habits such as drinking or nightlife",
            pattern_with_proxy=(
                "Social habits (drinking, nightlife) appear to be how this client interprets a 'similar "
                "lifestyle'."
            ),
            pattern_plain=(
                "Recent rejections repeatedly cite lifestyle differences, which may mean 'similar lifestyle' "
                "has a narrower meaning than currently recorded."
            ),
            trait_phrase="social / nightlife-oriented lifestyle",
            trait=_trait_social_lifestyle,
        ),
    )
}


# ---- output ----


@dataclass(frozen=True)
class EvidenceItem:
    kind: str  # rejection | accepted
    ref_id: str
    text: str
    date: datetime | None = None
    highlight: bool = False  # rejection mentions the proxy (e.g. college pedigree)
    highlight_label: str | None = None  # plain-language tag, e.g. "mentions college pedigree"


@dataclass(frozen=True)
class MirrorCardDraft:
    rule_key: str
    stated_attribute: str
    stated_text: str
    observed_attribute: str
    observed_summary: str
    possible_pattern: str
    confidence: str  # high | medium | low
    mixed_evidence: bool
    evidence_summary: str
    evidence: tuple[EvidenceItem, ...]
    supporting_feedback_ids: tuple[str, ...]
    similar_accepted_decision_ids: tuple[str, ...]
    supporting_count: int
    proxy_count: int
    accepted_count: int


# ---- helpers ----


def describe_candidate_traits(c: CandidateIn) -> str:
    parts: list[str] = []
    if c.career_level:
        parts.append({"senior": "strong career", "mid": "mid-level career", "early": "early-career"}.get(
            c.career_level, f"{c.career_level} career"))
    if c.education_tier:
        parts.append({"prestigious": "prestigious college", "standard": "non-prestigious college"}.get(
            c.education_tier, f"{c.education_tier} college"))
    if not parts and c.career:
        parts.append(c.career)
    return ", ".join(parts) if parts else "profile details not recorded"


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _eligible(signal: SignalIn, cutoff: datetime) -> bool:
    created = as_utc(signal.created_at)
    return (
        signal.category not in _IGNORED_CATEGORIES
        and signal.violation_type not in _IGNORED_VIOLATION_TYPES
        and (created is None or created >= cutoff)
    )


def _signal_dimension(signal: SignalIn) -> str:
    """The signal's observed dimension, derived from its category if it was never tagged."""
    if signal.observed_dimension:
        return signal.observed_dimension
    return infer_dimension(FeedbackCategory(signal.category), signal.attribute, signal.evidence).value


def _matches(signal: SignalIn, dimensions: frozenset[str]) -> bool:
    return _signal_dimension(signal) in dimensions


def _confidence(supporting: int, accepted: int, mixed: bool) -> str:
    if accepted >= 1 and supporting >= 4:
        level = 3
    elif accepted >= 1:
        level = 2
    else:
        level = 1
    if mixed:  # conflicting behaviour never raises confidence; it lowers it one step
        level = max(1, level - 1)
    return {3: "high", 2: "medium", 1: "low"}[level]


def build_card(
    rule: MirrorRule,
    pref: PreferenceIn,
    feedback: list[FeedbackIn],
    accepted: list[AcceptedIn],
    client_location: str | None,
    now: datetime,
) -> MirrorCardDraft | None:
    cutoff = now - timedelta(days=RECENT_DAYS)

    supporting: list[tuple[FeedbackIn, SignalIn | None, SignalIn | None]] = []
    for fb in feedback:
        eligible = [s for s in fb.signals if _eligible(s, cutoff)]
        base = next((s for s in eligible if _matches(s, rule.base_dimensions)), None)
        proxy = (
            next((s for s in eligible if _matches(s, rule.proxy_dimensions)), None)
            if rule.proxy_phrase
            else None
        )
        # one rejection note counts once, however many of its signals match
        if base or proxy:
            supporting.append((fb, base, proxy))

    n = len(supporting)
    if n < MIN_SUPPORTING_REJECTIONS:  # evidence threshold: no card from one rejection
        return None

    supporting.sort(key=lambda t: as_utc(t[0].created_at) or now, reverse=True)
    base_count = sum(1 for _, b, _p in supporting if b)
    # a single signal that matches both base and proxy is not counted as a separate proxy mention
    proxy_count = sum(1 for _, b, p in supporting if p is not None and p is not b)
    use_proxy = bool(rule.proxy_phrase) and proxy_count >= 2

    similar = [(a, rule.candidate_trait(a.candidate, client_location)) for a in accepted]
    similar = [(a, d) for a, d in similar if d]
    accepted_count = len(similar)
    mixed = accepted_count >= 2

    confidence = _confidence(n, accepted_count, mixed)

    pattern = rule.pattern_with_proxy if use_proxy else rule.pattern_plain
    if mixed:
        pattern = (
            f"Mixed evidence: {pattern} However, the client has also accepted {accepted_count} similar "
            "profiles, so this may not be a consistent rule."
        )

    if use_proxy:
        observed = (
            f"{_plural(base_count, 'recent rejection')} mention {rule.base_phrase}; "
            f"{proxy_count} mention {rule.proxy_phrase}."
        )
        example_count = proxy_count
    else:
        observed = f"{_plural(n, 'recent rejection')} mention {rule.base_phrase}."
        example_count = n

    if accepted_count:
        evidence_summary = (
            f"{_plural(example_count, 'rejection example')} + "
            f"{_plural(accepted_count, 'similar accepted profile')}"
        )
    else:
        evidence_summary = f"{_plural(example_count, 'rejection example')}; no similar accepted profile yet"

    items: list[EvidenceItem] = []
    for fb, base, proxy in supporting:
        picked = proxy if (use_proxy and proxy) else (base or proxy)
        assert picked is not None
        items.append(
            EvidenceItem(
                kind="rejection",
                ref_id=fb.id,
                text=picked.evidence,
                date=as_utc(fb.created_at),
                highlight=bool(use_proxy and proxy),
                highlight_label=f"mentions {rule.proxy_phrase}" if use_proxy and proxy else None,
            )
        )
    for a, _detail in similar:
        items.append(
            EvidenceItem(
                kind="accepted",
                ref_id=a.decision_id,
                text=f"Accepted similar profile: {describe_candidate_traits(a.candidate)}",
                date=as_utc(a.decided_at),
            )
        )

    return MirrorCardDraft(
        rule_key=rule.key,
        stated_attribute=rule.stated_attribute,
        stated_text=rule.stated_template.format(strength=STRENGTH_WORDS.get(pref.type, "important")),
        observed_attribute=rule.observed_attribute,
        observed_summary=observed,
        possible_pattern=pattern,
        confidence=confidence,
        mixed_evidence=mixed,
        evidence_summary=evidence_summary,
        evidence=tuple(items),
        supporting_feedback_ids=tuple(fb.id for fb, _b, _p in supporting),
        similar_accepted_decision_ids=tuple(a.decision_id for a, _d in similar),
        supporting_count=n,
        proxy_count=proxy_count,
        accepted_count=accepted_count,
    )


def compute_mirror_cards(
    preferences: list[PreferenceIn],
    feedback: list[FeedbackIn],
    accepted: list[AcceptedIn],
    client_location: str | None = None,
    now: datetime | None = None,
) -> list[MirrorCardDraft]:
    """All cards whose evidence threshold is met. Order: highest confidence first."""
    now = now or datetime.now(UTC)
    stated = {p.attribute: p for p in preferences}
    cards: list[MirrorCardDraft] = []
    for rule in MIRROR_RULES.values():
        pref = stated.get(rule.stated_attribute)
        if pref is None:  # no stated preference => nothing to compare behaviour against
            continue
        card = build_card(rule, pref, feedback, accepted, client_location, now)
        if card:
            cards.append(card)
    order = {"high": 0, "medium": 1, "low": 2}
    cards.sort(key=lambda c: (order[c.confidence], -c.supporting_count))
    return cards
