// Mirrors backend/app/schemas/*. Keep in sync with the Pydantic models.

export type Status = "RED" | "AMBER" | "GREEN";
export type Confidence = "high" | "medium" | "low";
export type PreferenceType = "dealbreaker" | "strong" | "soft";

export type FeedbackCategory =
  | "values_lifestyle"
  | "intellectual_fit"
  | "career_education"
  | "family_background"
  | "children_family_plans"
  | "location_distance"
  | "smoking_alcohol"
  | "age"
  | "communication_personality"
  | "attraction_first_impression"
  | "other"
  | "unclear";

export type ViolationType =
  | "dealbreaker"
  | "stated_preference"
  | "soft_preference"
  | "new_signal"
  | "not_a_preference_violation"
  | "unclear";

export type ReasonSource =
  | "dealbreaker"
  | "stated_preference"
  | "past_rejection"
  | "observed_pattern"
  | "confirmed_signal";

export interface ClientSummary {
  id: string;
  name: string;
  age: number;
  location: string;
}

export interface Preference {
  id: string;
  attribute: string;
  label: string;
  value: Record<string, unknown>;
  preference_type: PreferenceType;
  source: "onboarding" | "human_confirmed";
  created_at: string;
}

export interface Decision {
  id: string;
  candidate_id: string;
  candidate_name: string;
  matchmaker_id: string;
  status: "shared" | "accepted" | "rejected";
  rejection_reason_category: string | null;
  shared_at: string;
}

export interface EvidenceItem {
  kind: "rejection" | "accepted";
  ref_id: string;
  text: string;
  date: string | null;
  highlight: boolean;
  highlight_label?: string | null;
}

export interface MirrorCard {
  id: string;
  client_id: string;
  rule_key: string;
  status: "suggested" | "confirmed" | "dismissed";
  human_confirmed: boolean;
  stated_attribute: string;
  stated_text: string;
  observed_attribute: string;
  observed_summary: string;
  possible_pattern: string;
  confidence: Confidence;
  mixed_evidence: boolean;
  evidence_summary: string;
  evidence: EvidenceItem[];
  supporting_count: number;
  confirmed_at: string | null;
  advisory_note: string;
}

export interface MirrorResponse {
  client_id: string;
  suggestions: MirrorCard[];
  confirmed: MirrorCard[];
}

export interface ClientDetail extends ClientSummary {
  profile_summary: string;
  preferences: Preference[];
  recent_decisions: Decision[];
  preference_mirror: MirrorCard[];
}

export interface Candidate {
  id: string;
  name: string;
  age: number;
  location: string;
  smokes: boolean | null;
  drinks: boolean | null;
  wants_children: boolean | null;
  willing_to_relocate: boolean | null;
  education: string | null;
  education_tier: string | null;
  career: string | null;
  career_level: string | null;
  values_lifestyle: { tags?: string[]; family_setup?: string; social_style?: string };
  bio: string;
}

export interface Reason {
  code: string;
  message: string;
  source: ReasonSource;
  evidence: string;
  refs: string[];
}

export interface ProfileCheckResult {
  status: Status;
  status_label: string;
  summary: string;
  client: { id: string; name: string };
  candidate: { id: string; name: string };
  blocking_reasons: Reason[];
  warnings: Reason[];
  positive_signals: Reason[];
  notes: Reason[];
  preference_mirror: MirrorCard | null;
}

export interface StructuredSignal {
  category: FeedbackCategory;
  // Finer behavioural tag the AI picks from a fixed list; carried back on save unchanged.
  observed_dimension?: string | null;
  attribute: string;
  violated_stated_preference: boolean;
  violation_type: ViolationType;
  confidence: Confidence;
  explanation: string;
  evidence: string;
}

export interface StructureResponse {
  signals: StructuredSignal[];
  demo_mode: boolean;
  provider: string;
  notice: string | null;
}

export interface SampleNote {
  id: string;
  label: string;
  note: string;
}

export interface SaveFeedbackResponse {
  feedback_id: string;
  decision_id: string | null;
  signal_count: number;
  created_at: string;
  preference_mirror: MirrorCard[];
}
