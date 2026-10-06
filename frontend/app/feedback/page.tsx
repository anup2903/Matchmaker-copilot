"use client";

import { CheckCircle2, Loader2, Save, Sparkles } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { FeedbackResult } from "@/components/feedback-result";
import { EmptyState, ErrorState, Field, LoadingBlock, PageHeader, Pill } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import type { SaveFeedbackResponse, StructureResponse, StructuredSignal } from "@/lib/types";

export default function FeedbackPage() {
  const lists = useAsync(async () => {
    const [clients, samples, health] = await Promise.all([
      api.clients(),
      api.sampleNotes(),
      api.health().catch(() => null),
    ]);
    return { clients, samples, aiConfigured: health?.llm_mode === "configured" };
  });

  const [clientId, setClientId] = useState("");
  const [note, setNote] = useState("");

  const [analysing, setAnalysing] = useState(false);
  const [structured, setStructured] = useState<StructureResponse | null>(null);
  const [signals, setSignals] = useState<StructuredSignal[]>([]);
  const [analyseError, setAnalyseError] = useState<{ message: string; fallbackAvailable: boolean } | null>(null);

  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState<SaveFeedbackResponse | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  // A different note or client makes any earlier result stale.
  useEffect(() => {
    setStructured(null);
    setSignals([]);
    setSaved(null);
    setAnalyseError(null);
    setSaveError(null);
  }, [clientId, note]);

  async function structure(useDemoMode = false) {
    if (!clientId || !note.trim()) return;
    setAnalysing(true);
    setAnalyseError(null);
    setSaved(null);
    try {
      const res = await api.structureFeedback(clientId, note.trim(), useDemoMode);
      setStructured(res);
      setSignals(res.signals);
    } catch (e) {
      setStructured(null);
      setSignals([]);
      setAnalyseError(
        e instanceof ApiError
          ? { message: e.message, fallbackAvailable: e.fallbackAvailable }
          : { message: "Something went wrong. Please retry.", fallbackAvailable: false },
      );
    } finally {
      setAnalysing(false);
    }
  }

  async function save() {
    if (!clientId || signals.length === 0) return;
    setSaving(true);
    setSaveError(null);
    try {
      setSaved(
        await api.saveFeedback({
          client_id: clientId,
          rejection_note: note.trim(),
          matchmaker_id: "A",
          candidate_id: null,
          signals,
        }),
      );
    } catch (e) {
      setSaveError(e instanceof ApiError ? e.message : "Could not save. Please retry.");
    } finally {
      setSaving(false);
    }
  }

  if (lists.loading) return <LoadingBlock label="Loading…" />;
  if (lists.error || !lists.data) return <ErrorState message={lists.error ?? "No data"} onRetry={lists.reload} title="Couldn't reach the backend" />;
  const { clients, samples, aiConfigured } = lists.data;
  const client = clients.find((c) => c.id === clientId);
  const canStructure = Boolean(clientId && note.trim()) && !analysing;
  const mirrorNow = saved?.preference_mirror.filter((m) => m.status === "suggested") ?? [];

  return (
    <>
      <PageHeader
        title="Structure feedback"
        subtitle="Paste what the client said about a profile. AI turns it into clear, reusable signals — you check them, edit if needed, and save."
      />

      {!aiConfigured && (
        <p className="mb-6 rounded-2xl border border-line-strong bg-sand/60 px-4 py-3 text-sm text-ink-soft">
          <strong className="font-medium text-ink">AI isn&apos;t connected yet.</strong> Add <code className="rounded bg-white px-1">LLM_API_KEY</code> and{" "}
          <code className="rounded bg-white px-1">LLM_MODEL</code> to your <code className="rounded bg-white px-1">.env</code> to use a real model. Until then a
          built-in demo extractor handles the notes.
        </p>
      )}

      <div className="grid gap-8 lg:grid-cols-2">
        <section className="space-y-4">
          <Field label="Client" htmlFor="fb-client">
            <select id="fb-client" className="input" value={clientId} onChange={(e) => setClientId(e.target.value)}>
              <option value="">Select a client…</option>
              {clients.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Rejection note" htmlFor="note">
            <textarea
              id="note"
              className="input min-h-[200px] resize-y text-[15px] leading-relaxed"
              placeholder="Paste or type the client's feedback in their own words…"
              value={note}
              maxLength={4000}
              onChange={(e) => setNote(e.target.value)}
            />
          </Field>

          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-ink-muted">Try a sample:</span>
            {samples.map((s) => (
              <button key={s.id} type="button" className="btn-chip" onClick={() => setNote(s.note)}>
                {s.label}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-3">
            <button type="button" className="btn-primary" disabled={!canStructure} onClick={() => structure(false)}>
              {analysing ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <Sparkles className="h-4 w-4" aria-hidden />}
              {analysing ? "Analysing rejection…" : "Structure feedback"}
            </button>
            {!clientId && <span className="text-xs text-ink-muted">Pick a client first.</span>}
          </div>
        </section>

        <section className="min-w-0 space-y-4" aria-live="polite">
          <div className="flex items-center justify-between gap-2">
            <h2 className="serif text-xl font-medium">Structured result</h2>
            {structured?.demo_mode && <Pill tone="outline">Demo mode</Pill>}
            {structured && !structured.demo_mode && <Pill tone="outline">AI</Pill>}
          </div>

          {analysing && <LoadingBlock label="Analysing rejection…" />}

          {analyseError && (
            <div className="space-y-3">
              <ErrorState message={analyseError.message} title="Couldn't structure this note" onRetry={() => structure(false)} />
              {analyseError.fallbackAvailable && (
                <button type="button" className="btn-secondary" onClick={() => structure(true)}>
                  Use demo mode instead
                </button>
              )}
            </div>
          )}

          {!analysing && !analyseError && !structured && (
            <EmptyState title="Nothing structured yet">Pick a sample or paste your own note, then press “Structure feedback”.</EmptyState>
          )}

          {structured && !analysing && (
            <>
              {structured.notice && <p className="text-xs text-ink-muted">{structured.notice}</p>}
              <p className="text-sm text-ink-muted">
                {signals.length} {signals.length === 1 ? "signal" : "signals"} found. These are suggestions — check them against the note.
              </p>
              <FeedbackResult
                signals={signals}
                disabled={saving || saved !== null}
                onChange={(i, patch) => setSignals((prev) => prev.map((s, idx) => (idx === i ? { ...s, ...patch } : s)))}
                onRemove={(i) => setSignals((prev) => prev.filter((_, idx) => idx !== i))}
              />

              {saveError && <ErrorState message={saveError} title="Couldn't save feedback" onRetry={save} />}

              {!saved ? (
                <div className="flex items-center gap-3">
                  <button type="button" className="btn-primary" disabled={saving || signals.length === 0} onClick={save}>
                    {saving ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <Save className="h-4 w-4" aria-hidden />}
                    {saving ? "Saving…" : "Save feedback"}
                  </button>
                  <span className="text-xs text-ink-muted">Adds these signals to {client?.name ?? "the client"}&apos;s history.</span>
                </div>
              ) : (
                <div className="card p-5">
                  <p className="flex items-center gap-2 text-sm font-medium text-ink">
                    <CheckCircle2 className="h-4 w-4 text-gold-deep" aria-hidden /> Saved {saved.signal_count}{" "}
                    {saved.signal_count === 1 ? "signal" : "signals"} to {client?.name}&apos;s history.
                  </p>
                  <p className="mt-1 text-sm text-ink-muted">
                    {mirrorNow.length > 0
                      ? `${mirrorNow.length} Preference Mirror suggestion${mirrorNow.length === 1 ? "" : "s"} for ${client?.name} awaiting your review.`
                      : "No new Preference Mirror pattern yet — more evidence is needed."}
                  </p>
                  {clientId && (
                    <Link href={`/clients/${clientId}`} className="mt-2 inline-block text-sm font-medium text-forest underline underline-offset-2">
                      Review {client?.name}&apos;s Preference Mirror →
                    </Link>
                  )}
                </div>
              )}
            </>
          )}
        </section>
      </div>
    </>
  );
}
