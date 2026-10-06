"use client";

import { Loader2, SearchCheck } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { CandidateCard } from "@/components/candidate-card";
import { ClientCard } from "@/components/client-card";
import { PreferenceMirrorCard } from "@/components/preference-mirror";
import { ReasonList } from "@/components/reason-list";
import { StatusBadge } from "@/components/status-badge";
import { EmptyState, ErrorState, Field, LoadingBlock, PageHeader, SectionTitle } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import type { ProfileCheckResult } from "@/lib/types";
import { STATUS_STYLE, cn } from "@/lib/utils";

// Quick-pick scenarios for the demo path (resolved by name, so they only show if the seed data is present).
const SCENARIOS = [
  { label: "Ananya + smoker", client: "Ananya", candidate: "Rhea T." },
  { label: "Ananya + long distance", client: "Ananya", candidate: "Veer A." },
  { label: "Ananya + strong match", client: "Ananya", candidate: "Meher L." },
  { label: "Ananya + mirror pattern", client: "Ananya", candidate: "Rey D." },
];

export function CheckProfileView() {
  const params = useSearchParams();
  const lists = useAsync(async () => {
    const [clients, candidates] = await Promise.all([api.clients(), api.candidates()]);
    return { clients, candidates };
  });

  const [clientId, setClientId] = useState(params.get("client") ?? "");
  const [candidateId, setCandidateId] = useState("");
  const [result, setResult] = useState<ProfileCheckResult | null>(null);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const clientDetail = useAsync(() => api.client(clientId), clientId || null);
  const mirror = useAsync(() => api.mirror(clientId), clientId || null);

  const candidate = useMemo(
    () => lists.data?.candidates.find((c) => c.id === candidateId) ?? null,
    [lists.data, candidateId],
  );

  const runCheck = useCallback(async (cid: string, kid: string) => {
    setChecking(true);
    setError(null);
    try {
      setResult(await api.profileCheck(cid, kid));
    } catch (e) {
      setResult(null);
      setError(e instanceof ApiError ? e.message : "The check failed. Please retry.");
    } finally {
      setChecking(false);
    }
  }, []);

  // Selecting something new invalidates the previous result.
  useEffect(() => {
    setResult(null);
    setError(null);
  }, [clientId, candidateId]);

  function pick(clientName: string, candidateName: string) {
    const c = lists.data?.clients.find((x) => x.name === clientName);
    const k = lists.data?.candidates.find((x) => x.name === candidateName);
    if (!c || !k) return;
    setClientId(c.id);
    setCandidateId(k.id);
    void runCheck(c.id, k.id);
  }

  function onMirrorChange() {
    mirror.reload();
    clientDetail.reload();
    // A confirm / dismiss changes how future checks behave, so refresh the current verdict immediately.
    if (clientId && candidateId && result) void runCheck(clientId, candidateId);
  }

  if (lists.loading) return <LoadingBlock label="Loading clients and candidates…" />;
  if (lists.error || !lists.data)
    return <ErrorState message={lists.error ?? "No data"} onRetry={lists.reload} title="Couldn't reach the backend" />;

  const { clients, candidates } = lists.data;
  const canCheck = Boolean(clientId && candidateId) && !checking;
  const mirrorCards = [...(mirror.data?.suggestions ?? []), ...(mirror.data?.confirmed ?? [])];

  return (
    <>
      <PageHeader
        title="Check a profile"
        subtitle="Choose a client and a candidate before sharing. Dealbreakers are checked by fixed rules — the AI never decides a block."
      />

      <div className="card mb-8 p-5">
        <div className="grid items-end gap-4 md:grid-cols-[1fr_1fr_auto]">
          <Field label="Client" htmlFor="client">
            <select id="client" className="input" value={clientId} onChange={(e) => setClientId(e.target.value)}>
              <option value="">Select a client…</option>
              {clients.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} · {c.location}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Candidate" htmlFor="candidate">
            <select id="candidate" className="input" value={candidateId} onChange={(e) => setCandidateId(e.target.value)}>
              <option value="">Select a candidate…</option>
              {candidates.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} · {c.location}
                </option>
              ))}
            </select>
          </Field>
          <button type="button" className="btn-primary" disabled={!canCheck} onClick={() => runCheck(clientId, candidateId)}>
            {checking ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <SearchCheck className="h-4 w-4" aria-hidden />}
            {checking ? "Checking…" : "Check profile"}
          </button>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-line pt-3">
          <span className="text-xs text-ink-muted">Try:</span>
          {SCENARIOS.map((s) => (
            <button key={s.label} type="button" className="btn-chip" onClick={() => pick(s.client, s.candidate)}>
              {s.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-8 lg:grid-cols-[300px_1fr]">
        <aside className="space-y-4 self-start">
          {clientDetail.data ? (
            <ClientCard client={clientDetail.data} summary={clientDetail.data.profile_summary} preferences={clientDetail.data.preferences} compact />
          ) : (
            <EmptyState title="No client selected">Pick a client to see what they have told us they want.</EmptyState>
          )}
          {candidate ? (
            <CandidateCard candidate={candidate} />
          ) : (
            <EmptyState title="No candidate selected">Missing attributes are shown as “Unknown”, never guessed.</EmptyState>
          )}
          {clientDetail.data && (
            <Link href={`/clients/${clientDetail.data.id}`} className="block text-center text-sm text-ink-muted underline-offset-2 hover:text-ink hover:underline">
              Open {clientDetail.data.name}'s full profile →
            </Link>
          )}
        </aside>

        <div className="min-w-0 space-y-8">
          {checking && !result && <LoadingBlock label="Checking profile…" />}
          {error && <ErrorState message={error} onRetry={canCheck ? () => runCheck(clientId, candidateId) : undefined} title="Couldn't check this profile" />}

          {!result && !checking && !error && (
            <EmptyState title="No result yet">Select a client and a candidate, then press “Check profile”.</EmptyState>
          )}

          {result && (
            <section className="space-y-6" aria-live="polite">
              <div className={cn("rounded-2xl border px-6 py-5", STATUS_STYLE[result.status].bg, STATUS_STYLE[result.status].border)}>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <StatusBadge status={result.status} />
                  <p className="text-sm text-ink-muted">
                    {result.client.name} <span aria-hidden>×</span> {result.candidate.name}
                  </p>
                </div>
                <p className="serif mt-4 text-[26px] font-medium leading-snug text-ink">{result.summary}</p>
                <p className="mt-1 text-sm text-ink-soft">{STATUS_STYLE[result.status].hint}</p>
              </div>

              <ReasonList
                title="Blocking reasons"
                reasons={result.blocking_reasons}
                variant="block"
                emptyText="No dealbreaker is violated by a known candidate attribute."
              />
              <ReasonList
                title="Warnings"
                reasons={result.warnings}
                variant="warn"
                emptyText="No material warnings."
              />
              <ReasonList title="Positive matches" reasons={result.positive_signals} variant="positive" emptyText="No stored preference is clearly satisfied." />
              <ReasonList title="Minor notes" reasons={result.notes} variant="note" />
            </section>
          )}

          {clientId && (
            <section>
              <SectionTitle hint="Advisory — what decisions suggest vs. what the client says">
                Preference Mirror{clientDetail.data ? ` · ${clientDetail.data.name}` : ""}
              </SectionTitle>
              {mirror.loading && !mirror.data && <LoadingBlock label="Loading Preference Mirror…" />}
              {mirror.error && <ErrorState message={mirror.error} onRetry={mirror.reload} />}
              {mirror.data && mirrorCards.length === 0 && (
                <EmptyState title="No pattern to show">
                  Not enough saved evidence for this client yet. A pattern needs at least two supporting rejections.
                </EmptyState>
              )}
              <div className="space-y-4">
                {mirrorCards.map((card) => (
                  <PreferenceMirrorCard
                    key={card.id}
                    card={card}
                    onChange={onMirrorChange}
                    relevantToCandidate={result?.preference_mirror?.id === card.id}
                  />
                ))}
              </div>
            </section>
          )}
        </div>
      </div>
    </>
  );
}
