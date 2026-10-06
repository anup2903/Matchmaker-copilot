"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/check-profile", label: "Check Profile" },
  { href: "/feedback", label: "Structure Feedback" },
  { href: "/", label: "Clients" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [demo, setDemo] = useState(false);

  // Only shown when the AI key is missing and the deterministic fallback is active.
  useEffect(() => {
    api
      .health()
      .then((h) => setDemo(h.llm_mode === "demo"))
      .catch(() => undefined);
  }, []);

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" || pathname.startsWith("/clients") : pathname === href || pathname.startsWith(`${href}/`);

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-line bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-8 gap-y-2 px-4 py-3 sm:px-6 lg:px-10">
          <Link href="/" className="flex items-center gap-2.5" aria-label="Matchmaker Copilot home">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-gold-deep text-[11px] font-semibold lowercase text-white">
              tdc
            </span>
            <span className="serif text-[17px] font-semibold text-ink">The Date Crew</span>
            <span className="hidden rounded-full bg-sand px-2 py-0.5 text-[11px] font-medium text-ink-soft sm:inline">Copilot</span>
          </Link>

          <nav className="flex flex-1 items-center gap-1 overflow-x-auto" aria-label="Primary">
            {NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                aria-current={isActive(item.href) ? "page" : undefined}
                className={cn(
                  "whitespace-nowrap rounded-full px-3.5 py-1.5 text-sm transition-colors",
                  isActive(item.href) ? "bg-sand font-semibold text-ink" : "text-ink-soft hover:text-ink",
                )}
              >
                {item.label}
              </Link>
            ))}
          </nav>

          {demo && (
            <span
              className="rounded-full border border-line-strong px-2.5 py-1 text-[11px] font-medium text-ink-muted"
              title="No LLM_API_KEY is configured, so rejection notes use the built-in demo extractor."
            >
              Demo mode
            </span>
          )}
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:px-10 lg:py-10">{children}</main>
    </div>
  );
}
