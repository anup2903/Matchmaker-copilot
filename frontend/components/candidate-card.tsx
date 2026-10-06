import { MapPin } from "lucide-react";
import type { Candidate } from "@/lib/types";
import { cn, yesNoUnknown } from "@/lib/utils";

function Fact({ label, value }: { label: string; value: boolean | null }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1.5 text-sm">
      <dt className="text-ink-muted">{label}</dt>
      <dd className={cn(value === null ? "italic text-ink-faint" : "font-medium text-ink")}>{yesNoUnknown(value)}</dd>
    </div>
  );
}

export function CandidateCard({ candidate }: { candidate: Candidate }) {
  const tags = candidate.values_lifestyle?.tags ?? [];
  return (
    <div className="card p-5">
      <p className="label mb-2">Candidate</p>
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="serif text-xl font-medium">{candidate.name}</h3>
        <span className="text-sm text-ink-muted">{candidate.age}</span>
      </div>
      <p className="mt-0.5 flex items-center gap-1.5 text-sm text-ink-muted">
        <MapPin className="h-3.5 w-3.5" aria-hidden /> {candidate.location}
      </p>

      <dl className="mt-3 divide-y divide-line border-t border-line">
        <Fact label="Smokes" value={candidate.smokes} />
        <Fact label="Drinks" value={candidate.drinks} />
        <Fact label="Wants children" value={candidate.wants_children} />
        <Fact label="Willing to relocate" value={candidate.willing_to_relocate} />
      </dl>

      <div className="mt-3 space-y-0.5 border-t border-line pt-3 text-sm text-ink-soft">
        <p>{candidate.career ?? <span className="italic text-ink-faint">Career unknown</span>}</p>
        <p className="text-ink-muted">{candidate.education ?? <span className="italic text-ink-faint">Education unknown</span>}</p>
      </div>

      {tags.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {tags.map((t) => (
            <span key={t} className="rounded-full bg-sand px-2.5 py-0.5 text-[11px] text-ink-soft">
              {t}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
