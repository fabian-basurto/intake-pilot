"use client";

import { useMemo, useState } from "react";
import StatusPill from "./StatusPill";
import { compareReviews, type ChangeKind } from "@/lib/compare";
import { GROUP_LABELS, type ReviewResult } from "@/lib/types";

export interface CompareRun {
  id: string;
  name: string;
  completedAt: number;
  review: ReviewResult;
}

interface Props {
  current: CompareRun;
  previous: CompareRun[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

const CHANGE_LABEL: Record<ChangeKind, { label: string; className: string }> = {
  resolved: { label: "Resolved", className: "text-teal-800 bg-teal-50 border-teal-200" },
  new_gap: { label: "New gap", className: "text-amber-900 bg-amber-50 border-amber-300" },
  changed: { label: "Changed", className: "text-slate-700 bg-slate-50 border-slate-300" },
  same: { label: "Unchanged", className: "text-slate-500 bg-white border-slate-200" },
};

function timeLabel(ts: number) {
  return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export default function ComparePanel({ current, previous, selectedId, onSelect }: Props) {
  const [showUnchanged, setShowUnchanged] = useState(false);
  const prev = previous.find((p) => p.id === selectedId) ?? previous[0];
  const cmp = useMemo(() => (prev ? compareReviews(prev.review, current.review) : null), [prev, current]);
  if (!prev || !cmp) return null;

  const visible = cmp.items.filter((i) => showUnchanged || i.change !== "same");
  const samePacket = prev.name === current.name;

  return (
    <section className="card p-5" aria-labelledby="compare-heading">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs font-medium text-slate-500">Compare</div>
          <h2 id="compare-heading" className="mt-0.5 text-base font-semibold text-navy">
            How findings changed between packets
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Previous analysis includes any staff verifications made at the time. {samePacket && "Same file analyzed twice."}
          </p>
        </div>
        <label className="text-xs text-slate-600">
          Compare against
          <select
            value={prev.id}
            onChange={(e) => onSelect(e.target.value)}
            className="ml-2 rounded border border-slate-300 bg-white px-2 py-1 text-xs"
          >
            {previous.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} · {timeLabel(p.completedAt)} · {p.review.attentionCount} item{p.review.attentionCount === 1 ? "" : "s"}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Cell label="Previous" value={`${cmp.attentionBefore}`} sub={`${prev.name}`} tone={cmp.attentionBefore ? "amber" : "teal"} />
        <Cell label="Current" value={`${cmp.attentionAfter}`} sub={`${current.name}`} tone={cmp.attentionAfter ? "amber" : "teal"} />
        <Cell label="Resolved" value={`${cmp.resolved}`} sub="gaps now found" tone={cmp.resolved ? "teal" : "muted"} />
        <Cell label="New gaps" value={`${cmp.newGaps}`} sub="not found now" tone={cmp.newGaps ? "amber" : "muted"} />
      </div>

      <div className="mt-4 flex items-center justify-between">
        <div className="text-xs font-semibold text-slate-600">
          {visible.length === 0 ? "No differences between the two analyses." : `${visible.length} item${visible.length === 1 ? "" : "s"} shown`}
        </div>
        <label className="text-xs text-slate-500 inline-flex items-center gap-1.5">
          <input type="checkbox" checked={showUnchanged} onChange={(e) => setShowUnchanged(e.target.checked)} />
          Show unchanged ({cmp.same})
        </label>
      </div>

      {visible.length > 0 && (
        <div className="mt-2 overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-slate-500 border-b border-slate-200">
                <th className="py-1.5 pr-3 font-medium">Item</th>
                <th className="py-1.5 pr-3 font-medium">Previous</th>
                <th className="py-1.5 pr-3 font-medium">Current</th>
                <th className="py-1.5 font-medium">Change</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((i) => (
                <tr key={i.id} className="border-b border-slate-100 align-top">
                  <td className="py-2 pr-3">
                    <div className="font-medium text-slate-800">{i.label}</div>
                    <div className="text-slate-400">{GROUP_LABELS[i.group]}</div>
                  </td>
                  <td className="py-2 pr-3">
                    <StatusPill status={i.before} small />
                    <div className="mt-0.5 text-slate-600 max-w-[220px] truncate" title={i.beforeValue ?? ""}>
                      {i.beforeValue ?? "—"}
                      {i.beforePage !== null && <span className="text-slate-400"> · p{i.beforePage}</span>}
                    </div>
                  </td>
                  <td className="py-2 pr-3">
                    <StatusPill status={i.after} small />
                    <div className="mt-0.5 text-slate-600 max-w-[220px] truncate" title={i.afterValue ?? ""}>
                      {i.afterValue ?? "—"}
                      {i.afterPage !== null && <span className="text-slate-400"> · p{i.afterPage}</span>}
                    </div>
                  </td>
                  <td className="py-2">
                    <span className={`inline-block rounded-full border px-2 py-0.5 text-[11px] font-medium ${CHANGE_LABEL[i.change].className}`}>
                      {CHANGE_LABEL[i.change].label}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function Cell({ label, value, sub, tone }: { label: string; value: string; sub: string; tone: "teal" | "amber" | "muted" }) {
  const cls =
    tone === "teal" ? "border-teal-200 bg-teal-50 text-teal-800" : tone === "amber" ? "border-amber-200 bg-amber-50 text-amber-800" : "border-slate-200 bg-slate-50 text-slate-600";
  return (
    <div className={`rounded-md border px-3 py-2 ${cls}`}>
      <div className="text-[11px] font-medium opacity-80">{label}</div>
      <div className="text-lg font-semibold leading-tight">{value}</div>
      <div className="text-[11px] truncate opacity-80" title={sub}>
        {sub}
      </div>
    </div>
  );
}
