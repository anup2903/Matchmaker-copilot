"""Shared vocabulary for client preferences and feedback categories.

Preference `value` JSON shapes (documented here so seed data, checker and UI agree):

    smoking                 {"allowed": false}
    drinking                {"allowed": bool}
    children                {"wants_children": bool}
    location                {"mode": "same_city"} | {"mode": "max_distance_km", "max_km": 300}
    age                     {"min": 28, "max": 36}
    similar_lifestyle       {"tags": ["fitness", "travel"]}
    open_to_relocation      {"open": true}
    intellectual_compatibility | ambition | family_compatibility   {"importance": "high"}
    mirror:<rule_key>       soft signal created by a matchmaker-confirmed Preference Mirror card
"""

from enum import StrEnum
from typing import Any


class PreferenceType(StrEnum):
    dealbreaker = "dealbreaker"
    strong = "strong"
    soft = "soft"


class FeedbackCategory(StrEnum):
    values_lifestyle = "values_lifestyle"
    intellectual_fit = "intellectual_fit"
    career_education = "career_education"
    family_background = "family_background"
    children_family_plans = "children_family_plans"
    location_distance = "location_distance"
    smoking_alcohol = "smoking_alcohol"
    age = "age"
    communication_personality = "communication_personality"
    attraction_first_impression = "attraction_first_impression"
    other = "other"
    unclear = "unclear"


class ObservedDimension(StrEnum):
    """Closed vocabulary of *observed* behavioural dimensions.

    The rejection-structuring LLM picks exactly one of these per signal (it is constrained to the list,
    the way `category` is). It is a finer tag than `category` — e.g. a career_education rejection splits
    into `education_prestige` vs `career_ambition` — so the Preference Mirror can group behaviour by a
    stable tag instead of brittle keyword matching, and new patterns are added as data (see
    preference_mirror.MIRROR_RULES) rather than code.

    Deliberately excludes sensitive dimensions (religion, caste, health, physical appearance): the system
    never infers those.
    """

    intellectual_depth = "intellectual_depth"
    education_prestige = "education_prestige"
    career_ambition = "career_ambition"
    financial_stability = "financial_stability"
    family_background = "family_background"
    family_setup = "family_setup"  # living arrangements, proximity to / living with parents
    values_lifestyle = "values_lifestyle"  # general values / daily-rhythm mismatch
    lifestyle_social = "lifestyle_social"  # drinking, nightlife, partying
    lifestyle_health = "lifestyle_health"  # fitness, diet, routine
    hobbies_interests = "hobbies_interests"
    communication_style = "communication_style"
    emotional_maturity = "emotional_maturity"
    physical_distance = "physical_distance"
    relocation = "relocation"
    age_gap = "age_gap"
    children_plans = "children_plans"
    smoking = "smoking"
    drinking = "drinking"
    first_impression = "first_impression"
    timing_availability = "timing_availability"  # practical: busy, travelling, pausing — not about the profile
    other = "other"
    unclear = "unclear"


class ViolationType(StrEnum):
    dealbreaker = "dealbreaker"
    stated_preference = "stated_preference"
    soft_preference = "soft_preference"
    new_signal = "new_signal"
    not_a_preference_violation = "not_a_preference_violation"
    unclear = "unclear"


class Confidence(StrEnum):
    high = "high"
    medium = "medium"
    low = "low"


# Violation types that mean "the client had already told us this".
VIOLATION_TYPES_STATED = frozenset(
    {ViolationType.dealbreaker, ViolationType.stated_preference, ViolationType.soft_preference}
)

# Feedback category -> client preference attributes a candidate could *violate*.
# (open_to_relocation describes the client, so a distance rejection does not "violate" it —
#  that tension is exactly what the Preference Mirror surfaces instead.)
CATEGORY_PREFERENCE_ATTRIBUTES: dict[FeedbackCategory, tuple[str, ...]] = {
    FeedbackCategory.values_lifestyle: ("similar_lifestyle",),
    FeedbackCategory.intellectual_fit: ("intellectual_compatibility",),
    FeedbackCategory.career_education: ("ambition",),
    FeedbackCategory.family_background: ("family_compatibility",),
    FeedbackCategory.children_family_plans: ("children",),
    FeedbackCategory.location_distance: ("location",),
    FeedbackCategory.smoking_alcohol: ("smoking", "drinking"),
    FeedbackCategory.age: ("age",),
    FeedbackCategory.communication_personality: (),
    FeedbackCategory.attraction_first_impression: (),
    FeedbackCategory.other: (),
    FeedbackCategory.unclear: (),
}

# Used in sentences such as "Client rejected 3 recent profiles citing <phrase>".
CATEGORY_PHRASES: dict[str, str] = {
    "location_distance": "long distance",
    "smoking_alcohol": "smoking / drinking",
    "career_education": "career",
    "children_family_plans": "children / family plans",
    "values_lifestyle": "lifestyle differences",
    "intellectual_fit": "intellectual fit",
    "family_background": "family background",
    "age": "age",
    "communication_personality": "communication / personality",
    "attraction_first_impression": "first impression",
}

STRENGTH_WORDS: dict[str, str] = {
    "dealbreaker": "a dealbreaker",
    "strong": "important",
    "soft": "somewhat important",
}

# Short labels for the observed dimensions (shown in prompts and, if needed, the UI).
DIMENSION_LABELS: dict[str, str] = {
    "intellectual_depth": "intellectual depth of conversation",
    "education_prestige": "college / education prestige",
    "career_ambition": "career ambition or trajectory",
    "financial_stability": "financial stability",
    "family_background": "family background",
    "family_setup": "living arrangements / proximity to parents",
    "values_lifestyle": "general values or daily-life rhythm",
    "lifestyle_social": "social habits (drinking, nightlife, partying)",
    "lifestyle_health": "health habits (fitness, diet, routine)",
    "hobbies_interests": "hobbies and interests",
    "communication_style": "communication or conversation style",
    "emotional_maturity": "emotional maturity",
    "physical_distance": "physical distance / location",
    "relocation": "willingness to relocate",
    "age_gap": "age difference",
    "children_plans": "plans about children",
    "smoking": "smoking",
    "drinking": "drinking / alcohol",
    "first_impression": "first impression / attraction",
    "timing_availability": "timing or availability (busy, travelling, paused)",
    "other": "something else",
    "unclear": "unclear",
}

# Short attribute names used when a model omits `attribute` (kept lowercase, like the attributes models write).
DIMENSION_SHORT_LABELS: dict[str, str] = {
    "intellectual_depth": "intellectual compatibility",
    "education_prestige": "college pedigree",
    "career_ambition": "career",
    "financial_stability": "financial stability",
    "family_background": "family background",
    "family_setup": "living arrangements",
    "values_lifestyle": "lifestyle",
    "lifestyle_social": "drinking and nightlife",
    "lifestyle_health": "health habits",
    "hobbies_interests": "hobbies and interests",
    "communication_style": "communication style",
    "emotional_maturity": "emotional maturity",
    "physical_distance": "distance",
    "relocation": "relocation",
    "age_gap": "age gap",
    "children_plans": "children",
    "smoking": "smoking",
    "drinking": "drinking",
    "first_impression": "first impression",
    "timing_availability": "timing / availability",
    "other": "other",
    "unclear": "overall fit",
}

# Each observed dimension rolls up to one feedback category (used to keep profile-check warnings and
# Mirror suggestions from double-reporting the same behaviour).
DIMENSION_CATEGORY: dict[str, FeedbackCategory] = {
    "intellectual_depth": FeedbackCategory.intellectual_fit,
    "education_prestige": FeedbackCategory.career_education,
    "career_ambition": FeedbackCategory.career_education,
    "financial_stability": FeedbackCategory.career_education,
    "family_background": FeedbackCategory.family_background,
    "family_setup": FeedbackCategory.values_lifestyle,
    "values_lifestyle": FeedbackCategory.values_lifestyle,
    "lifestyle_social": FeedbackCategory.smoking_alcohol,
    "lifestyle_health": FeedbackCategory.values_lifestyle,
    "hobbies_interests": FeedbackCategory.values_lifestyle,
    "communication_style": FeedbackCategory.communication_personality,
    "emotional_maturity": FeedbackCategory.communication_personality,
    "physical_distance": FeedbackCategory.location_distance,
    "relocation": FeedbackCategory.location_distance,
    "age_gap": FeedbackCategory.age,
    "children_plans": FeedbackCategory.children_family_plans,
    "smoking": FeedbackCategory.smoking_alcohol,
    "drinking": FeedbackCategory.smoking_alcohol,
    "first_impression": FeedbackCategory.attraction_first_impression,
    "timing_availability": FeedbackCategory.other,
    "other": FeedbackCategory.other,
    "unclear": FeedbackCategory.unclear,
}

# Keyword hints used ONLY by the deterministic fallbacks (demo extractor + seed) to assign a dimension
# when no real LLM did. The live LLM picks the dimension directly. (attribute + evidence text, lowercased.)
_DIMENSION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "education_prestige": ("college", "pedigree", "universit", "degree", "education", "alma mater", "ivy", "iit", "iim"),
    "career_ambition": ("career", "ambiti", "driven", "trajectory", "salary", "job", "profession", "role"),
    "family_setup": ("parents", "hometown", "live near", "move in", "joint family", "living arrangement", "settle near"),
    "lifestyle_social": ("drink", "alcohol", "party", "parties", "nightlife", "going out", "pub", "bar"),
    "lifestyle_health": ("fitness", "gym", "diet", "workout", "health"),
    "smoking": ("smok", "cigarette", "vape"),
    "timing_availability": ("busy", "trip", "swamped", "schedule", "pause", "hold off", "travel", "not ready", "on hold", "revisit"),
}


def infer_dimension(category: FeedbackCategory, attribute: str, evidence: str) -> ObservedDimension:
    """Deterministically map a (category, attribute, evidence) to a dimension.

    Used by the demo extractor and the seed so behaviour is identical with or without an LLM key; the real
    LLM provides the dimension directly. Kept intentionally small — keyword nuance lives here, not in the
    Mirror engine, so the engine only ever groups by the clean tag.
    """
    text = f"{attribute} {evidence}".lower()

    def has(dim: str) -> bool:
        return any(k in text for k in _DIMENSION_KEYWORDS[dim])

    if category == FeedbackCategory.intellectual_fit:
        return ObservedDimension.education_prestige if has("education_prestige") else ObservedDimension.intellectual_depth
    if category == FeedbackCategory.career_education:
        if has("education_prestige") and not has("career_ambition"):
            return ObservedDimension.education_prestige
        return ObservedDimension.career_ambition
    if category == FeedbackCategory.family_background:
        return ObservedDimension.family_background
    if category == FeedbackCategory.values_lifestyle:
        if has("family_setup"):
            return ObservedDimension.family_setup
        if has("lifestyle_social"):
            return ObservedDimension.lifestyle_social
        if has("lifestyle_health"):
            return ObservedDimension.lifestyle_health
        return ObservedDimension.values_lifestyle
    if category == FeedbackCategory.smoking_alcohol:
        if has("smoking"):
            return ObservedDimension.smoking
        return ObservedDimension.drinking
    if category == FeedbackCategory.location_distance:
        return ObservedDimension.physical_distance
    if category == FeedbackCategory.children_family_plans:
        return ObservedDimension.children_plans
    if category == FeedbackCategory.age:
        return ObservedDimension.age_gap
    if category == FeedbackCategory.communication_personality:
        return ObservedDimension.communication_style
    if category == FeedbackCategory.attraction_first_impression:
        return ObservedDimension.first_impression
    if category == FeedbackCategory.unclear:
        return ObservedDimension.unclear
    if has("timing_availability"):
        return ObservedDimension.timing_availability
    return ObservedDimension.other


def describe_preference(attribute: str, value: dict[str, Any] | None) -> str:
    """Short human-readable label for a stored preference (used as quotable evidence)."""
    v = value or {}
    if attribute == "smoking":
        return "Non-smoker" if v.get("allowed") is False else "Smoking is fine"
    if attribute == "drinking":
        return "Non-drinker" if v.get("allowed") is False else "Drinking is fine"
    if attribute == "children":
        return "Wants children" if v.get("wants_children", True) else "Does not want children"
    if attribute == "location":
        if v.get("mode") == "max_distance_km":
            return f"Within {v.get('max_km')} km"
        return "Same city preferred"
    if attribute == "age":
        return f"Age {v.get('min', '?')}–{v.get('max', '?')}"
    if attribute == "similar_lifestyle":
        tags = ", ".join(v.get("tags", []))
        return f"Similar lifestyle ({tags})" if tags else "Similar lifestyle"
    if attribute == "open_to_relocation":
        return "Open to relocation" if v.get("open", True) else "Not open to relocation"
    if attribute == "intellectual_compatibility":
        return "Intellectual compatibility"
    if attribute == "ambition":
        return "Ambition"
    if attribute == "family_compatibility":
        return "Family compatibility"
    if attribute.startswith("mirror:"):
        return str(v.get("description") or attribute)
    return attribute.replace("_", " ").capitalize()


def relevant_attributes(category: FeedbackCategory, attribute: str) -> set[str]:
    relevant = set(CATEGORY_PREFERENCE_ATTRIBUTES.get(category, ()))
    if category == FeedbackCategory.smoking_alcohol:
        text = attribute.lower()
        if "smok" in text:
            return relevant & {"smoking"}
        if "drink" in text or "alcohol" in text:
            return relevant & {"drinking"}
    return relevant


def classify_violation(
    category: FeedbackCategory, preferences: list[tuple[str, str]], attribute: str = ""
) -> ViolationType:
    """Deterministically decide how a rejection category relates to the client's stored preferences.

    `preferences` is a list of (attribute, preference_type). Returns dealbreaker / stated_preference /
    soft_preference when a semantically relevant preference exists, else new_signal.
    """
    relevant = relevant_attributes(category, attribute)
    types = {ptype for attr, ptype in preferences if attr in relevant}
    if PreferenceType.dealbreaker in types:
        return ViolationType.dealbreaker
    if PreferenceType.strong in types:
        return ViolationType.stated_preference
    if PreferenceType.soft in types:
        return ViolationType.soft_preference
    return ViolationType.new_signal
