"use client";

import { ArrowUpRight } from "lucide-react";
import Link from "next/link";
import { ClientCard } from "@/components/client-card";
import { ErrorState, LoadingBlock, SectionTitle } from "@/components/ui";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import type { ClientDetail } from "@/lib/types";

function HeroButton({ href, children, filled }: { href: string; children: string; filled?: boolean }) {
  return (
    <Link
      href={href}
      className={
        filled
          ? "inline-flex items-center gap-3 rounded-full bg-forest py-2 pl-2 pr-6 text-sm font-medium text-white ring-1 ring-white/20 hover:bg-forest-dark"
          : "inline-flex items-center gap-3 rounded-full py-2 pl-2 pr-6 text-sm font-medium text-white/90 ring-1 ring-white/25 hover:bg-white/10"
      }
    >
      <span className="flex h-8 w-8 items-center justify-center rounded-full bg-white/15">
        <ArrowUpRight className="h-4 w-4" aria-hidden />
      </span>
      {children}
    </Link>
  );
}

export default function HomePage() {
  const clients = useAsync<ClientDetail[]>(async () => {
    const list = await api.clients();
    return Promise.all(list.map((c) => api.client(c.id)));
  });

  return (
    <>
      <section className="mb-12 rounded-3xl bg-espresso px-6 py-12 sm:px-12 sm:py-16">
        <p className="mb-4 text-xs font-semibold uppercase tracking-[0.18em] text-gold">Matchmaker Copilot</p>
        <h1 className="max-w-2xl !text-[44px] !leading-[1.1] text-gold sm:!text-[56px]">What your clients really want.</h1>
        <p className="mt-5 max-w-xl text-[17px] leading-relaxed text-white/80">
          Remember what each client says they want, what they have turned down, and what their decisions suggest. The AI
          suggests — you decide.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <HeroButton href="/check-profile" filled>
            Check a profile
          </HeroButton>
          <HeroButton href="/feedback">Structure a rejection note</HeroButton>
        </div>
      </section>

      <SectionTitle hint="Open a client to see their Preference Mirror">Your clients</SectionTitle>
      {clients.loading && <LoadingBlock label="Loading clients…" />}
      {clients.error && <ErrorState message={clients.error} onRetry={clients.reload} title="Couldn't load clients" />}
      {clients.data && (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {clients.data.map((c) => (
            <ClientCard
              key={c.id}
              client={c}
              summary={c.profile_summary}
              preferences={c.preferences.filter((p) => !p.attribute.startsWith("mirror:"))}
              mirrorCount={c.preference_mirror.filter((m) => m.status === "suggested").length}
              href={`/clients/${c.id}`}
            />
          ))}
        </div>
      )}
    </>
  );
}
