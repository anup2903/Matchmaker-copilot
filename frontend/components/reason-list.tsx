import type { Reason } from "@/lib/types";
import { SOURCE_LABEL, cn } from "@/lib/utils";

type Variant = "block" | "warn" | "positive" | "note";

const DOT: Record<Variant, string> = {
  block: "bg-state-red-solid",
  warn: "bg-state-amber-solid",
  positive: "bg-state-green-solid",
  note: "bg-ink-faint",
};

function ReasonItem({ reason, variant }: { reason: Reason; variant: Variant }) {
  return (
    <li className="flex gap-3 rounded-xl border border-line bg-white px-4 py-3">
      <span className={cn("mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full", DOT[variant])} aria-hidden />
      <div className="min-w-0">
        <p className="text-sm font-medium text-ink">{reason.message}</p>
        <p className="mt-1 text-xs leading-relaxed text-ink-muted">
          <span className="mr-2 rounded-full bg-sand px-2 py-0.5 font-medium text-ink-soft">{SOURCE_LABEL[reason.source]}</span>
          {reason.evidence}
        </p>
      </div>
    </li>
  );
}

export function ReasonList({
  title,
  reasons,
  variant,
  emptyText,
}: {
  title: string;
  reasons: Reason[];
  variant: Variant;
  emptyText?: string;
}) {
  if (reasons.length === 0 && !emptyText) return null;
  return (
    <section aria-label={title}>
      <h2 className="mb-2">
        {title} <span className="ml-1 font-normal text-ink-faint">{reasons.length}</span>
      </h2>
      {reasons.length === 0 ? (
        <p className="rounded-xl border border-dashed border-line-strong px-4 py-3 text-sm text-ink-muted">{emptyText}</p>
      ) : (
        <ul className="space-y-2">
          {reasons.map((r) => (
            <ReasonItem key={r.code + r.evidence} reason={r} variant={variant} />
          ))}
        </ul>
      )}
    </section>
  );
}
