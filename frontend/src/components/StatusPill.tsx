import type { RuleStatus } from "@/lib/types";

const STYLES: Record<RuleStatus, { label: string; className: string }> = {
  ok: { label: "Found", className: "bg-teal-50 text-teal-800 border-teal-200" },
  not_found: { label: "Not found in packet", className: "bg-amber-50 text-amber-800 border-amber-200" },
  needs_review: { label: "Needs staff review", className: "bg-amber-50 text-amber-900 border-amber-300" },
  info: { label: "Informational", className: "bg-slate-50 text-slate-600 border-slate-200" },
};

export function statusLabel(status: RuleStatus, overridden?: boolean) {
  if (overridden) return "Verified by staff";
  return STYLES[status].label;
}

export default function StatusPill({ status, overridden, small }: { status: RuleStatus; overridden?: boolean; small?: boolean }) {
  const base = overridden ? { label: "Verified by staff", className: "bg-teal-50 text-teal-800 border-teal-200" } : STYLES[status];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border font-medium whitespace-nowrap ${small ? "px-2 py-0.5 text-[11px]" : "px-2.5 py-0.5 text-xs"} ${base.className}`}
    >
      <span
        className={`inline-block h-1.5 w-1.5 rounded-full ${
          status === "ok" || overridden ? "bg-teal-600" : status === "info" ? "bg-slate-400" : "bg-amber-500"
        }`}
      />
      {base.label}
    </span>
  );
}
