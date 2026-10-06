"use client";

import { AlertTriangle, Inbox, Loader2, RotateCw } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div className="max-w-2xl">
        <h1>{title}</h1>
        {subtitle && <p className="mt-2 text-[15px] leading-relaxed text-ink-muted">{subtitle}</p>}
      </div>
      {actions}
    </div>
  );
}

export function SectionTitle({ children, hint }: { children: ReactNode; hint?: ReactNode }) {
  return (
    <div className="mb-3 flex items-baseline justify-between gap-3">
      <h2 className="serif text-xl font-medium">{children}</h2>
      {hint && <span className="text-xs text-ink-muted">{hint}</span>}
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-ink-muted" role="status">
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
      {label}
    </span>
  );
}

export function LoadingBlock({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="card flex items-center justify-center px-6 py-14">
      <Spinner label={label} />
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
  title = "Something went wrong",
}: {
  message: string;
  onRetry?: () => void;
  title?: string;
}) {
  return (
    <div className="rounded-2xl border border-state-red-border bg-state-red-bg px-5 py-4" role="alert">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-state-red-fg" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-state-red-fg">{title}</p>
          <p className="mt-0.5 text-sm text-ink-soft">{message}</p>
        </div>
        {onRetry && (
          <button type="button" onClick={onRetry} className="btn-secondary shrink-0 !px-3.5 !py-1.5 text-xs">
            <RotateCw className="h-3.5 w-3.5" aria-hidden /> Retry
          </button>
        )}
      </div>
    </div>
  );
}

export function EmptyState({ title, children, icon }: { title: string; children?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-line-strong px-6 py-10 text-center">
      <div className="mb-2 text-gold">{icon ?? <Inbox className="h-6 w-6" aria-hidden />}</div>
      <p className="text-sm font-medium text-ink">{title}</p>
      {children && <p className="mt-1 max-w-md text-sm text-ink-muted">{children}</p>}
    </div>
  );
}

/** Small neutral tag. Never green/amber/red — those are reserved for status. */
export function Pill({ children, tone = "neutral", className }: { children: ReactNode; tone?: "neutral" | "ink" | "outline"; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-medium",
        tone === "neutral" && "bg-sand text-ink-soft",
        tone === "ink" && "bg-forest text-white",
        tone === "outline" && "bg-white text-ink-soft ring-1 ring-inset ring-line-strong",
        className,
      )}
    >
      {children}
    </span>
  );
}

export function Field({ label, children, htmlFor }: { label: string; children: ReactNode; htmlFor?: string }) {
  return (
    <label className="block" htmlFor={htmlFor}>
      <span className="label mb-1.5 block">{label}</span>
      {children}
    </label>
  );
}
