"use client";

import { ArrowLeft, ClipboardCheck } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { PreferenceChip } from "@/components/client-card";
import { PreferenceMirrorCard } from "@/components/preference-mirror";
import { EmptyState, ErrorState, LoadingBlock, PageHeader, Pill, SectionTitle } from "@/components/ui";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import type { MirrorCard, Preference, PreferenceType } from "@/lib/types";
import { PREFERENCE_TYPE_LABEL, categoryLabel, formatDate } from "@/lib/utils";

const GROUPS: PreferenceType[] = ["dealbreaker", "strong", "soft"];

export default function ClientPage() {
  const { id } = useParams<{ id: string }>();
  const client = useAsync(() => api.client(id), id);

  function applyCard(updated: MirrorCard) {
    if (!client.data) return;
    // dismissed cards leave the list; confirmed cards update in place. Preferences are re-read after a confirm.
    const next = client.data.preference_mirror
      .map((c) => (c.id === updated.id ? updated : c))
      .filter((c) => c.status !== "dismissed");
    client.setData({ ...client.data, preference_mirror: next });
    if (updated.status === "confirmed") client.reload();
  }

  if (client.loading && !client.data) return <LoadingBlock label="Loading client…" />;
  if (client.error) return <ErrorState message={client.error} onRetry={client.reload} title="Couldn't load this client" />;
  if (!client.data) return null;
  const c = client.data;
  const suggested = c.preference_mirror.filter((m) => m.status === "suggested");
  const confirmed = c.preference_mirror.filter((m) => m.status === "confirmed");

  return (
    <>
      <Link href="/" className="mb-4 inline-flex items-center gap-1.5 text-sm text-ink-muted hover:text-ink">
        <ArrowLeft className="h-3.5 w-3.5" aria-hidden /> All clients
      </Link>
      <PageHeader
        title={`${c.name}, ${c.age}`}
        subtitle={`${c.location} · ${c.profile_summary}`}
        actions={
          <Link href={`/check-profile?client=${c.id}`} className="btn-primary">
            <ClipboardCheck className="h-4 w-4" aria-hidden /> Check a profile for {c.name}
          </Link>
        }
      />

      <div className="grid gap-8 lg:grid-cols-5">
        <div className="space-y-8 lg:col-span-3">
          <section>
            <SectionTitle hint="What the client says">Stated preferences</SectionTitle>
            <div className="card divide-y divide-line">
              {GROUPS.map((type) => {
                const prefs = c.preferences.filter((p: Preference) => p.preference_type === type);
                if (prefs.length === 0) return null;
                return (
                  <div key={type} className="flex flex-col gap-2 px-5 py-3.5 sm:flex-row sm:items-start sm:gap-6">
                    <p className="label w-36 shrink-0 pt-1">{PREFERENCE_TYPE_LABEL[type]}</p>
                    <div className="flex flex-wrap gap-1.5">
                      {prefs.map((p) => (
                        <PreferenceChip key={p.id} preference={p} />
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          <section>
            <SectionTitle hint="What their decisions suggest — advisory only">Preference Mirror</SectionTitle>
            {suggested.length === 0 && confirmed.length === 0 ? (
              <EmptyState title="No pattern to show yet">
                A pattern appears only when there is enough saved evidence — at least two supporting rejections. One
                rejection is never enough.
              </EmptyState>
            ) : (
              <div className="space-y-4">
                {[...suggested, ...confirmed].map((card) => (
                  <PreferenceMirrorCard key={card.id} card={card} onChange={applyCard} />
                ))}
              </div>
            )}
          </section>
        </div>

        <section className="lg:col-span-2">
          <SectionTitle hint={`${c.recent_decisions.length} most recent`}>Recent decisions</SectionTitle>
          <ul className="card divide-y divide-line">
            {c.recent_decisions.map((d) => (
              <li key={d.id} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
                <div className="min-w-0">
                  <p className="truncate font-medium text-ink">{d.candidate_name}</p>
                  <p className="text-xs text-ink-muted">
                    {formatDate(d.shared_at)} · Matchmaker {d.matchmaker_id}
                    {d.rejection_reason_category && ` · ${categoryLabel(d.rejection_reason_category)}`}
                  </p>
                </div>
                <Pill tone={d.status === "accepted" ? "ink" : "outline"} className="shrink-0 capitalize">
                  {d.status}
                </Pill>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </>
  );
}
