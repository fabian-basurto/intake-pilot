"use client";

import RuleRow from "./RuleRow";
import { GROUP_LABELS, type Overrides, type ReviewerOverride, type RuleGroup, type RuleResult } from "@/lib/types";

interface Props {
  group: RuleGroup;
  items: RuleResult[];
  expandedId: string | null;
  onToggle: (id: string) => void;
  onOverride: (id: string, override: ReviewerOverride | null) => void;
}

export default function ChecklistGroup({ group, items, expandedId, onToggle, onOverride }: Props) {
  const flagged = items.filter((i) => i.status === "not_found" || i.status === "needs_review").length;
  // Flagged first, then found, then info — stable within each bucket.
  const order = (s: RuleResult["status"]) => (s === "not_found" || s === "needs_review" ? 0 : s === "ok" ? 1 : 2);
  const sorted = [...items].sort((a, b) => order(a.status) - order(b.status));

  return (
    <div className="card overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 bg-slate-50 border-b border-slate-200">
        <h3 className="text-xs font-semibold tracking-wide uppercase text-slate-600">{GROUP_LABELS[group]}</h3>
        <span className={`text-[11px] ${flagged ? "text-amber-800 font-medium" : "text-slate-500"}`}>
          {flagged ? `${flagged} need${flagged === 1 ? "s" : ""} attention` : "No gaps"}
        </span>
      </div>
      <ul>
        {sorted.map((item) => (
          <RuleRow key={item.id} item={item} expanded={expandedId === item.id} onToggle={() => onToggle(item.id)} onOverride={(o) => onOverride(item.id, o)} />
        ))}
      </ul>
    </div>
  );
}

export type { Overrides };
