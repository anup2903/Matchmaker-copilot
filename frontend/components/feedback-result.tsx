"use client";

import { Check, Pencil, Trash2 } from "lucide-react";
import { useState } from "react";
import type { Confidence, FeedbackCategory, StructuredSignal, ViolationType } from "@/lib/types";
import {
  CATEGORIES,
  CATEGORY_LABEL,
  CONFIDENCE_LABEL,
  DIMENSION_LABEL,
  VIOLATION_LABEL,
  VIOLATION_TYPES,
  cn,
  dimensionLabel,
  isStatedViolation,
} from "@/lib/utils";
import { Pill } from "./ui";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[9rem_1fr] items-baseline gap-3 py-2">
      <dt className="text-xs text-ink-muted">{label}</dt>
      <dd className="min-w-0 text-sm text-ink">{children}</dd>
    </div>
  );
}

function ConfidenceTag({ value }: { value: Confidence }) {
  const filled = value === "high" ? 3 : value === "medium" ? 2 : 1;
  return (
    <span className="inline-flex items-center gap-1.5 font-medium">
      <span className="flex gap-0.5" aria-hidden>
        {[1, 2, 3].map((i) => (
          <span key={i} className={cn("h-2.5 w-1.5 rounded-sm", i <= filled ? "bg-gold-deep" : "bg-line-strong")} />
        ))}
      </span>
      {CONFIDENCE_LABEL[value]}
    </span>
  );
}

function SignalCard({
  signal,
  index,
  total,
  onChange,
  onRemove,
  disabled,
}: {
  signal: StructuredSignal;
  index: number;
  total: number;
  onChange: (patch: Partial<StructuredSignal>) => void;
  onRemove: () => void;
  disabled: boolean;
}) {
  const [editing, setEditing] = useState(false);

  return (
    <li className="card">
      <div className="flex items-center justify-between gap-2 px-5 pt-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="serif text-lg font-medium">{CATEGORY_LABEL[signal.category]}</span>
          <Pill tone="outline">Extracted signal {index + 1}</Pill>
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            className="btn-chip gap-1"
            onClick={() => setEditing((v) => !v)}
            disabled={disabled}
            aria-pressed={editing}
          >
            {editing ? <Check className="h-3.5 w-3.5" aria-hidden /> : <Pencil className="h-3.5 w-3.5" aria-hidden />}
            {editing ? "Done" : "Edit"}
          </button>
          {total > 1 && (
            <button type="button" className="btn-chip" onClick={onRemove} disabled={disabled} aria-label={`Remove signal ${index + 1}`}>
              <Trash2 className="h-3.5 w-3.5" aria-hidden />
            </button>
          )}
        </div>
      </div>

      <dl className="divide-y divide-line px-5 pb-3 pt-1">
        {editing && (
          <Row label="Category">
            <select
              className="input !py-1.5"
              value={signal.category}
              onChange={(e) => onChange({ category: e.target.value as FeedbackCategory })}
              aria-label="Category"
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {CATEGORY_LABEL[c]}
                </option>
              ))}
            </select>
          </Row>
        )}
        <Row label="Specific reason">
          {editing ? (
            <select
              className="input !py-1.5"
              value={signal.observed_dimension ?? "other"}
              onChange={(e) => onChange({ observed_dimension: e.target.value })}
              aria-label="Specific reason"
            >
              {Object.entries(DIMENSION_LABEL).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          ) : (
            dimensionLabel(signal.observed_dimension) ?? signal.attribute
          )}
        </Row>
        <Row label="Stated preference violated?">
          <span className="font-medium">{signal.violated_stated_preference ? "Yes" : "No"}</span>
          <span className="ml-2 text-ink-muted">
            {editing ? (
              <select
                className="input !inline-block !w-auto !py-1.5"
                value={signal.violation_type}
                onChange={(e) => {
                  const violation_type = e.target.value as ViolationType;
                  onChange({ violation_type, violated_stated_preference: isStatedViolation(violation_type) });
                }}
                aria-label="Violation type"
              >
                {VIOLATION_TYPES.map((v) => (
                  <option key={v} value={v}>
                    {VIOLATION_LABEL[v]}
                  </option>
                ))}
              </select>
            ) : (
              <>({VIOLATION_LABEL[signal.violation_type]})</>
            )}
          </span>
        </Row>
        <Row label="Confidence">
          {editing ? (
            <select className="input !w-auto !py-1.5" value={signal.confidence} onChange={(e) => onChange({ confidence: e.target.value as Confidence })} aria-label="Confidence">
              {(["high", "medium", "low"] as Confidence[]).map((c) => (
                <option key={c} value={c}>
                  {CONFIDENCE_LABEL[c]}
                </option>
              ))}
            </select>
          ) : (
            <ConfidenceTag value={signal.confidence} />
          )}
        </Row>
        <Row label="Evidence">
          <span className="serif text-[15px] italic text-ink-soft">“{signal.evidence}”</span>
        </Row>
        <Row label="Why">
          {editing ? (
            <textarea className="input min-h-[4.5rem]" value={signal.explanation} maxLength={400} onChange={(e) => onChange({ explanation: e.target.value })} aria-label="Explanation" />
          ) : (
            <span className="text-ink-soft">{signal.explanation}</span>
          )}
        </Row>
      </dl>
    </li>
  );
}

export function FeedbackResult({
  signals,
  onChange,
  onRemove,
  disabled = false,
}: {
  signals: StructuredSignal[];
  onChange: (index: number, patch: Partial<StructuredSignal>) => void;
  onRemove: (index: number) => void;
  disabled?: boolean;
}) {
  return (
    <ul className="space-y-3" aria-label="Structured signals">
      {signals.map((s, i) => (
        <SignalCard
          key={`${i}-${s.evidence}`}
          signal={s}
          index={i}
          total={signals.length}
          onChange={(patch) => onChange(i, patch)}
          onRemove={() => onRemove(i)}
          disabled={disabled}
        />
      ))}
    </ul>
  );
}
