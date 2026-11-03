"use client";

import { useEffect, useState } from "react";

interface Props {
  draft: string;
  dirty: boolean;
  attentionCount: number;
  onChange: (text: string) => void;
  onRegenerate: () => void;
  onExport: () => void;
}

export default function DraftPanel({ draft, dirty, attentionCount, onChange, onRegenerate, onExport }: Props) {
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (!copied) return;
    const t = setTimeout(() => setCopied(false), 1800);
    return () => clearTimeout(t);
  }, [copied]);

  async function copy() {
    try {
      await navigator.clipboard.writeText(draft);
      setCopied(true);
    } catch {
      // Fallback for browsers without clipboard permission in this context.
      const ta = document.createElement("textarea");
      ta.value = draft;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      ta.remove();
      setCopied(true);
    }
  }

  return (
    <section className="card p-5" aria-labelledby="draft-heading">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs font-medium text-slate-500">Next action</div>
          <h2 id="draft-heading" className="mt-0.5 text-base font-semibold text-navy">
            {attentionCount > 0 ? "Draft request for missing or unclear information" : "Draft acknowledgement to referring office"}
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Draft for review. Edit freely. Nothing is sent from this screen.
            {dirty && " Edited by staff — regenerate to rebuild from current findings."}
          </p>
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={onExport} className="rounded-md border border-slate-300 text-slate-700 px-3 py-1.5 text-xs font-medium hover:bg-slate-50">
            Export summary (JSON)
          </button>
          {dirty && (
            <button type="button" onClick={onRegenerate} className="rounded-md border border-slate-300 text-slate-700 px-3 py-1.5 text-xs font-medium hover:bg-slate-50">
              Regenerate
            </button>
          )}
          <button type="button" onClick={copy} className="rounded-md bg-navy text-white px-3 py-1.5 text-xs font-semibold hover:bg-navy-soft">
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
      </div>
      <textarea
        value={draft}
        onChange={(e) => onChange(e.target.value)}
        spellCheck={false}
        rows={Math.min(22, Math.max(10, draft.split("\n").length + 1))}
        className="mt-3 w-full rounded-md border border-slate-200 bg-slate-50/50 px-3 py-2.5 text-sm leading-relaxed text-slate-800 focus:outline-none focus:ring-2 focus:ring-teal-500/40 focus:bg-white"
      />
    </section>
  );
}
