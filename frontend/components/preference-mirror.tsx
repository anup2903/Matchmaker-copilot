"use client";

import { Check, ChevronDown, X } from "lucide-react";
import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Confidence, MirrorCard } from "@/lib/types";
import { CONFIDENCE_LABEL, cn, formatDate } from "@/lib/utils";
import { Pill, Spinner } from "./ui";

function ConfidenceMeter({ level, mixed }: { level: Confidence; mixed: boolean }) {
  const filled = level === "high" ? 3 : level === "medium" ? 2 : 1;
  return (
    <span className="inline-flex items-center gap-2" aria-label={`Confidence: ${CONFIDENCE_LABEL[level]}`}>
      <span className="flex gap-0.5" aria-hidden>
        {[1, 2, 3].map((i) => (
          <span key={i} className={cn("h-3 w-1.5 rounded-sm", i <= filled ? "bg-gold-deep" : "bg-line-strong")} />
        ))}
      </span>
      <span className="text-sm font-semibold text-ink">{CONFIDENCE_LABEL[level]}</span>
      {mixed && <Pill tone="outline">Mixed evidence</Pill>}
    </span>
  );
}

export function PreferenceMirrorCard({
  card,
  onChange,
  relevantToCandidate = false,
  compact = false,
}: {
  card: MirrorCard;
  /** Called with the updated card after the matchmaker confirms or dismisses (dismissed => status "dismissed"). */
  onChange?: (card: MirrorCard) => void;
  relevantToCandidate?: boolean;
  compact?: boolean;
}) {
  const [busy, setBusy] = useState<"confirm" | "dismiss" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const confirmed = card.status === "confirmed";
  const rejections = card.evidence.filter((e) => e.kind === "rejection");
  const accepted = card.evidence.filter((e) => e.kind === "accepted");

  async function act(kind: "confirm" | "dismiss") {
    setBusy(kind);
    setError(null);
    try {
      const updated = kind === "confirm" ? await api.confirmMirror(card.id) : await api.dismissMirror(card.id);
      onChange?.(updated);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not save your decision. Please retry.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <article className="card overflow-hidden" aria-label="Preference Mirror pattern">
      <header className="flex flex-wrap items-center justify-between gap-2 px-5 pt-4">
        <div className="flex flex-wrap items-center gap-2">
          <p className="label">Preference Mirror</p>
          <Pill tone="outline">Suggestion</Pill>
          {relevantToCandidate && <Pill tone="ink">Relevant to this candidate</Pill>}
        </div>
        {confirmed && <Pill tone="ink">Confirmed by matchmaker</Pill>}
      </header>

      <div className="grid gap-4 px-5 py-4 md:grid-cols-2 md:gap-8">
        <section>
          <p className="mb-1 text-xs font-medium text-ink-muted">What the client says</p>
          <p className="serif text-lg leading-snug text-ink">{card.stated_text}</p>
        </section>
        <section>
          <p className="mb-1 text-xs font-medium text-ink-muted">What their decisions suggest</p>
          <p className="text-[15px] leading-snug text-ink-soft">{card.observed_summary}</p>
        </section>
      </div>

      <div className="mx-5 rounded-xl bg-sand/70 px-4 py-3.5">
        <p className="mb-1 text-xs font-medium text-gold-deep">Possible pattern</p>
        <p className="text-[15px] leading-relaxed text-ink">{card.possible_pattern}</p>
      </div>

      <div className="space-y-3 px-5 py-4">
        <div className="flex flex-wrap items-center gap-x-8 gap-y-2 text-sm">
          <div className="flex items-center gap-2">
            <span className="text-ink-muted">Confidence</span>
            <ConfidenceMeter level={card.confidence} mixed={card.mixed_evidence} />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-ink-muted">Evidence</span>
            <span className="text-ink">{card.evidence_summary}</span>
          </div>
        </div>

        {!compact && card.evidence.length > 0 && (
          <details className="group rounded-xl border border-line px-4 py-2.5 text-sm">
            <summary className="flex cursor-pointer list-none items-center justify-between font-medium text-ink-soft">
              Show evidence
              <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" aria-hidden />
            </summary>
            <ul className="mt-3 space-y-1.5 text-ink-soft">
              {rejections.map((e) => (
                <li key={`${e.kind}-${e.ref_id}`}>
                  <span className="text-ink-muted">Rejection{e.date ? ` · ${formatDate(e.date)}` : ""}: </span>“{e.text}”
                  {e.highlight && (
                    <span className="ml-1.5 text-[11px] font-medium text-gold-deep">
                      · {e.highlight_label ?? "supports the pattern above"}
                    </span>
                  )}
                </li>
              ))}
              {accepted.map((e) => (
                <li key={`${e.kind}-${e.ref_id}`}>{e.text}</li>
              ))}
            </ul>
          </details>
        )}

        {error && (
          <p className="text-sm text-state-red-fg" role="alert">
            {error}
          </p>
        )}

        {card.status === "suggested" && onChange && (
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <button type="button" className="btn-primary" disabled={busy !== null} onClick={() => act("confirm")}>
              {busy === "confirm" ? <Spinner /> : <Check className="h-4 w-4" aria-hidden />}
              Confirm as soft signal
            </button>
            <button type="button" className="btn-secondary" disabled={busy !== null} onClick={() => act("dismiss")}>
              {busy === "dismiss" ? <Spinner /> : <X className="h-4 w-4" aria-hidden />}
              Dismiss
            </button>
          </div>
        )}

        <p className="text-xs leading-relaxed text-ink-muted">
          {confirmed
            ? `Confirmed${card.confirmed_at ? ` on ${formatDate(card.confirmed_at)}` : ""}. Applied as a soft signal only — it can trigger a review, never a block.`
            : "Suggestion only — nothing changes unless you confirm it."}
        </p>
      </div>
    </article>
  );
}
