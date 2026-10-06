import { MapPin } from "lucide-react";
import Link from "next/link";
import type { ClientSummary, Preference } from "@/lib/types";
import { cn } from "@/lib/utils";

export function PreferenceChip({ preference }: { preference: Pick<Preference, "label" | "preference_type" | "source"> }) {
  const strength = preference.preference_type;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs",
        strength === "dealbreaker" && "bg-espresso font-medium text-white",
        strength === "strong" && "bg-white font-medium text-ink ring-1 ring-inset ring-line-strong",
        strength === "soft" && "bg-sand text-ink-soft",
      )}
      title={preference.source === "human_confirmed" ? "Soft signal confirmed by a matchmaker" : undefined}
    >
      {preference.label}
      {strength === "dealbreaker" && <span className="text-[10px] uppercase tracking-wide text-gold">dealbreaker</span>}
      {preference.source === "human_confirmed" && <span className="text-[10px] uppercase tracking-wide opacity-70">confirmed</span>}
    </span>
  );
}

export function ClientCard({
  client,
  summary,
  preferences,
  mirrorCount,
  href,
  compact = false,
}: {
  client: ClientSummary;
  summary?: string;
  preferences?: Preference[];
  mirrorCount?: number;
  href?: string;
  compact?: boolean;
}) {
  const body = (
    <div className={cn("card h-full p-5", href && "transition-shadow hover:shadow-pop")}>
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-sand font-serif text-lg font-medium text-gold-deep">
          {client.name.charAt(0)}
        </span>
        <div className="min-w-0">
          <h3 className="serif text-xl font-medium leading-tight">
            {client.name} <span className="font-sans text-sm font-normal text-ink-muted">· {client.age}</span>
          </h3>
          <p className="flex items-center gap-1 text-sm text-ink-muted">
            <MapPin className="h-3 w-3" aria-hidden /> {client.location}
          </p>
        </div>
      </div>
      {summary && !compact && <p className="mt-3 text-sm leading-relaxed text-ink-soft">{summary}</p>}
      {preferences && preferences.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-1.5">
          {preferences.map((p) => (
            <PreferenceChip key={p.id} preference={p} />
          ))}
        </div>
      )}
      {mirrorCount !== undefined && mirrorCount > 0 && (
        <p className="mt-4 border-t border-line pt-3 text-xs font-medium text-gold-deep">
          {mirrorCount} pattern{mirrorCount === 1 ? "" : "s"} to review
        </p>
      )}
    </div>
  );
  return href ? (
    <Link href={href} className="block h-full rounded-2xl">
      {body}
    </Link>
  ) : (
    body
  );
}
