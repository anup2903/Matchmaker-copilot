import type { Candidate, Confidence, FeedbackCategory, PreferenceType, ReasonSource, Status, ViolationType } from "./types";

export function cn(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

export const STATUS_STYLE: Record<
  Status,
  { label: string; word: string; fg: string; bg: string; border: string; solid: string; hint: string }
> = {
  RED: {
    label: "RED — BLOCKED",
    word: "Blocked",
    fg: "text-state-red-fg",
    bg: "bg-state-red-bg",
    border: "border-state-red-border",
    solid: "bg-state-red-solid",
    hint: "A client dealbreaker is violated by a known candidate detail.",
  },
  AMBER: {
    label: "AMBER — REVIEW",
    word: "Review",
    fg: "text-state-amber-fg",
    bg: "bg-state-amber-bg",
    border: "border-state-amber-border",
    solid: "bg-state-amber-solid",
    hint: "No hard blocker, but worth your judgement before sharing.",
  },
  GREEN: {
    label: "GREEN — GOOD TO SHARE",
    word: "Good to share",
    fg: "text-state-green-fg",
    bg: "bg-state-green-bg",
    border: "border-state-green-border",
    solid: "bg-state-green-solid",
    hint: "No hard conflict and no material warning found in the stored data.",
  },
};

export const SOURCE_LABEL: Record<ReasonSource, string> = {
  dealbreaker: "Dealbreaker",
  stated_preference: "Stated preference",
  past_rejection: "Past rejection",
  observed_pattern: "Observed pattern (unconfirmed)",
  confirmed_signal: "Confirmed soft signal",
};

export const CATEGORY_LABEL: Record<FeedbackCategory, string> = {
  values_lifestyle: "Values / lifestyle",
  intellectual_fit: "Intellectual fit",
  career_education: "Career / education",
  family_background: "Family background",
  children_family_plans: "Family / children plans",
  location_distance: "Location / distance",
  smoking_alcohol: "Smoking / alcohol",
  age: "Age",
  communication_personality: "Communication / personality",
  attraction_first_impression: "Attraction / first impression",
  other: "Other",
  unclear: "Unclear",
};

export const CATEGORIES = Object.keys(CATEGORY_LABEL) as FeedbackCategory[];

export const VIOLATION_LABEL: Record<ViolationType, string> = {
  dealbreaker: "Dealbreaker",
  stated_preference: "Stated preference",
  soft_preference: "Soft preference",
  new_signal: "New signal",
  not_a_preference_violation: "Not a preference violation",
  unclear: "Unclear",
};

export const VIOLATION_TYPES = Object.keys(VIOLATION_LABEL) as ViolationType[];

export const STATED_VIOLATION_TYPES: ViolationType[] = ["dealbreaker", "stated_preference", "soft_preference"];

export const isStatedViolation = (t: ViolationType) => STATED_VIOLATION_TYPES.includes(t);

export const CONFIDENCE_LABEL: Record<Confidence, string> = { high: "High", medium: "Medium", low: "Low" };

export const PREFERENCE_TYPE_LABEL: Record<PreferenceType, string> = {
  dealbreaker: "Dealbreaker",
  strong: "Strong preference",
  soft: "Soft preference",
};

export function categoryLabel(key: string): string {
  return CATEGORY_LABEL[key as FeedbackCategory] ?? key.replace(/_/g, " ");
}

// Short labels for observed-dimension tags (mirrors backend DIMENSION_LABELS).
export const DIMENSION_LABEL: Record<string, string> = {
  intellectual_depth: "Intellectual depth",
  education_prestige: "Education prestige",
  career_ambition: "Career ambition",
  financial_stability: "Financial stability",
  family_background: "Family background",
  family_setup: "Living arrangements",
  values_lifestyle: "Values / lifestyle",
  lifestyle_social: "Drinking / nightlife",
  lifestyle_health: "Health habits",
  hobbies_interests: "Hobbies / interests",
  communication_style: "Communication style",
  emotional_maturity: "Emotional maturity",
  physical_distance: "Distance",
  relocation: "Relocation",
  age_gap: "Age gap",
  children_plans: "Children plans",
  smoking: "Smoking",
  drinking: "Drinking",
  first_impression: "First impression",
  timing_availability: "Timing / availability",
  other: "Other",
  unclear: "Unclear",
};

export function dimensionLabel(key: string | null | undefined): string | null {
  if (!key) return null;
  return DIMENSION_LABEL[key] ?? key.replace(/_/g, " ");
}

/** Missing attributes are shown as "Unknown", never guessed. */
export function yesNoUnknown(value: boolean | null | undefined): string {
  if (value === null || value === undefined) return "Unknown";
  return value ? "Yes" : "No";
}

export function candidateSubtitle(c: Candidate): string {
  return `${c.age} · ${c.location}`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}
