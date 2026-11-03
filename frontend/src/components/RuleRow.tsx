"use client";

import { useState } from "react";
import StatusPill from "./StatusPill";
import { SOURCE_LABELS, type ReviewerOverride, type RuleResult } from "@/lib/types";

interface Props {
  item: RuleResult;
  expanded: boolean;
  onToggle: () => void;
  onOverride: (override: ReviewerOverride | null) => void;
}

export default function RuleRow({ item, expanded, onToggle, onOverride }: Props) {
  const [mode, setMode] = useState<"none" | "verify" | "correct">("none");
  const [note, setNote] = useState("");
  const [value, setValue] = useState(item.value ?? "");

  const flagged = item.status === "not_found" || item.status === "needs_review";
  const overridden = !!item.override;
  const evidencePage = item.evidence?.page ?? null;

  function submit() {
    if (mode === "verify") onOverride({ kind: "verified", note: note.trim() || undefined });
    if (mode === "correct") {
      if (!value.trim()) return;
      onOverride({ kind: "corrected", value: value.trim(), note: note.trim() || undefined });
    }
    setMode("none");
    setNote("");
  }

  return (
    <li id={`rule-${item.id}`} className={`border-b border-slate-100 last:border-b-0 scroll-mt-24 ${flagged ? "bg-amber-50/30" : ""}`}>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className="w-full text-left px-4 py-2.5 flex items-start gap-3 hover:bg-slate-50/80 transition-colors"
      >
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium text-slate-800">{item.label}</span>
            <StatusPill status={item.status} overridden={overridden} small />
            {item.level === "info" && !item.value && <span className="text-[11px] text-slate-400">not provided</span>}
          </div>
          <div className="mt-0.5 text-sm text-slate-700 truncate">
            {item.value ? item.value : <span className="text-slate-400 italic">{item.status === "ok" ? "Present" : "—"}</span>}
          </div>
        </div>
        <div className="shrink-0 text-right text-[11px] text-slate-500 pt-0.5">
          {evidencePage !== null ? `Evidence: page ${evidencePage}` : item.status === "ok" ? "Evidence: see detail" : "No evidence in upload"}
          <div className="text-slate-300 mt-0.5">{expanded ? "▴" : "▾"}</div>
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-4 pt-1 text-xs text-slate-700 space-y-3">
          <div>
            <div className="font-semibold text-slate-600 mb-0.5">Why</div>
            <p>{item.detail}</p>
            {item.override?.note && <p className="mt-1 text-slate-500">Staff note: {item.override.note}</p>}
          </div>

          {(item.fieldRecords.length > 0 || item.documentRecords.length > 0) && (
            <div>
              <div className="font-semibold text-slate-600 mb-1">Extraction evidence</div>
              <ul className="space-y-1">
                {item.fieldRecords.map((f) => (
                  <li key={f.field} className="rounded border border-slate-200 bg-white px-2.5 py-1.5">
                    <div className="flex flex-wrap gap-x-3 gap-y-0.5">
                      <span className="font-mono text-[11px] text-slate-500">{f.field}</span>
                      <span className="text-slate-600">{f.status.replace("_", " ")}</span>
                      {f.evidence.page !== null && <span className="text-slate-500">page {f.evidence.page}</span>}
                    </div>
                    {f.value && <div className="mt-0.5 text-slate-800">{f.value}</div>}
                    {f.evidence.excerpt && <blockquote className="mt-0.5 border-l-2 border-slate-200 pl-2 text-slate-600 italic">“{f.evidence.excerpt}”</blockquote>}
                    {f.note && <div className="mt-0.5 text-amber-800">{f.note}</div>}
                  </li>
                ))}
                {item.documentRecords.map((d) => (
                  <li key={d.category} className="rounded border border-slate-200 bg-white px-2.5 py-1.5">
                    <div className="flex flex-wrap gap-x-3 gap-y-0.5">
                      <span className="font-mono text-[11px] text-slate-500">{d.category}</span>
                      <span className="text-slate-600">{d.status.replace("_", " ")}</span>
                      {d.pages.length > 0 && <span className="text-slate-500">page{d.pages.length > 1 ? "s" : ""} {d.pages.join(", ")}</span>}
                    </div>
                    {d.excerpt && <blockquote className="mt-0.5 border-l-2 border-slate-200 pl-2 text-slate-600 italic">“{d.excerpt}”</blockquote>}
                    {d.note && <div className="mt-0.5 text-amber-800">{d.note}</div>}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div>
            <div className="font-semibold text-slate-600 mb-0.5">Checklist source</div>
            <ul className="text-slate-500 space-y-0.5">
              {item.source.map((s, i) => (
                <li key={i}>
                  {SOURCE_LABELS[s.pdf]}, page {s.page}: {s.section}
                </li>
              ))}
            </ul>
          </div>

          <div className="pt-1 border-t border-slate-100">
            {overridden ? (
              <button type="button" onClick={() => onOverride(null)} className="text-xs font-medium text-slate-600 underline underline-offset-2 hover:text-slate-900">
                Undo staff {item.override?.kind === "corrected" ? "correction" : "verification"}
              </button>
            ) : mode === "none" ? (
              <div className="flex flex-wrap gap-2">
                <button type="button" onClick={() => setMode("verify")} className="rounded-md border border-teal-600 text-teal-800 px-2.5 py-1 text-xs font-medium hover:bg-teal-50">
                  Mark as verified
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setValue(item.value ?? "");
                    setMode("correct");
                  }}
                  className="rounded-md border border-slate-300 text-slate-700 px-2.5 py-1 text-xs font-medium hover:bg-slate-50"
                >
                  Correct value
                </button>
              </div>
            ) : (
              <form
                className="space-y-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  submit();
                }}
              >
                {mode === "correct" && (
                  <label className="block">
                    <span className="text-slate-600">Corrected value</span>
                    <input
                      autoFocus
                      value={value}
                      onChange={(e) => setValue(e.target.value)}
                      className="mt-0.5 w-full rounded border border-slate-300 px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/40"
                    />
                  </label>
                )}
                <label className="block">
                  <span className="text-slate-600">Staff note (optional)</span>
                  <input
                    autoFocus={mode === "verify"}
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    placeholder={mode === "verify" ? "e.g. Confirmed by phone with referring office" : "e.g. Illegible on fax, confirmed with office"}
                    className="mt-0.5 w-full rounded border border-slate-300 px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/40"
                  />
                </label>
                <div className="flex gap-2">
                  <button type="submit" className="rounded-md bg-teal-700 text-white px-2.5 py-1 text-xs font-medium hover:bg-teal-800">
                    {mode === "verify" ? "Save verification" : "Save correction"}
                  </button>
                  <button type="button" onClick={() => setMode("none")} className="rounded-md px-2.5 py-1 text-xs text-slate-600 hover:bg-slate-100">
                    Cancel
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </li>
  );
}
