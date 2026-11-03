"use client";

import type { ReviewResult } from "@/lib/types";
import StatusPill from "./StatusPill";

interface Props {
  review: ReviewResult;
  modelLine: string;
  onJump: (ruleId: string) => void;
}

export default function SummaryCard({ review, modelLine, onJump }: Props) {
  const attention = review.status === "attention";
  const flagged = review.items.filter((i) => i.status === "not_found" || i.status === "needs_review");
  const verified = review.items.filter((i) => i.override).length;

  return (
    <section className="card p-5" aria-labelledby="summary-heading">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs font-medium text-slate-500">Referral review summary</div>
          <h2
            id="summary-heading"
            className={`mt-1 text-xl font-semibold tracking-tight ${attention ? "text-amber-800" : "text-teal-800"}`}
          >
            {review.headline}
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            {review.subline}
            {verified > 0 && ` · ${verified} verified or corrected by staff`}
          </p>
        </div>
        <div className="flex gap-2 text-xs">
          <Stat label="Found" value={review.counts.ok} tone="teal" />
          <Stat label="Not found" value={review.counts.not_found} tone="amber" />
          <Stat label="Staff review" value={review.counts.needs_review} tone="amber" />
        </div>
      </div>

      {flagged.length > 0 && (
        <div className="mt-4 rounded-md border border-amber-200 bg-amber-50/60">
          <div className="px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-amber-900 border-b border-amber-200">Action needed</div>
          <ul className="divide-y divide-amber-100">
            {flagged.map((i) => (
              <li key={i.id} className="flex items-start gap-3 px-3 py-2">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-slate-800">{i.label}</span>
                    <StatusPill status={i.status} small />
                  </div>
                  <p className="mt-0.5 text-xs text-slate-700">{i.detail}</p>
                </div>
                <button
                  type="button"
                  onClick={() => onJump(i.id)}
                  className="shrink-0 rounded-md border border-amber-300 bg-white px-2 py-1 text-[11px] font-medium text-amber-900 hover:bg-amber-100"
                >
                  Review
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="mt-3 text-[11px] text-slate-400">{modelLine}</p>
    </section>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone: "teal" | "amber" }) {
  const color = value === 0 ? "text-slate-500 border-slate-200 bg-slate-50" : tone === "teal" ? "text-teal-800 border-teal-200 bg-teal-50" : "text-amber-800 border-amber-200 bg-amber-50";
  return (
    <div className={`rounded-md border px-3 py-1.5 min-w-[72px] text-center ${color}`}>
      <div className="text-lg font-semibold leading-tight">{value}</div>
      <div className="text-[11px]">{label}</div>
    </div>
  );
}
