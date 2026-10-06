import { CheckCircle2, OctagonX, TriangleAlert } from "lucide-react";
import type { Status } from "@/lib/types";
import { STATUS_STYLE, cn } from "@/lib/utils";

const ICON = { RED: OctagonX, AMBER: TriangleAlert, GREEN: CheckCircle2 } as const;

export function StatusBadge({ status, size = "lg" }: { status: Status; size?: "sm" | "lg" }) {
  const s = STATUS_STYLE[status];
  const Icon = ICON[status];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2.5 rounded-full border font-semibold tracking-wide",
        s.border,
        s.fg,
        size === "lg" ? "bg-white px-4 py-1.5 text-[13px] uppercase tracking-[0.12em]" : "px-2.5 py-1 text-xs " + s.bg,
      )}
      data-status={status}
    >
      <Icon className={size === "lg" ? "h-4 w-4" : "h-3.5 w-3.5"} aria-hidden />
      {s.label}
    </span>
  );
}
