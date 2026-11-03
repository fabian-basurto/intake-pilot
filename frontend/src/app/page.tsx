"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import IntakePanel, { type AnalyzeStage, type IntakePhase, type IntakeSelection } from "@/components/IntakePanel";
import SummaryCard from "@/components/SummaryCard";
import ChecklistGroup from "@/components/ChecklistGroup";
import DraftPanel from "@/components/DraftPanel";
import SourcePanel from "@/components/SourcePanel";
import ComparePanel, { type CompareRun } from "@/components/ComparePanel";
import { ApiError, analyzePacket, reviewWithOverrides } from "@/lib/api";
import type { AnalyzeResponse, Overrides, ReviewResult, ReviewerOverride, RuleGroup } from "@/lib/types";

const FIELD_GROUPS: RuleGroup[] = ["patient", "insurance", "order", "contact"];
const HISTORY_LIMIT = 6;

export default function Home() {
  const [selection, setSelection] = useState<IntakeSelection | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [stage, setStage] = useState<AnalyzeStage>("uploading");
  const [uploadPct, setUploadPct] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<{ message: string; retryable: boolean } | null>(null);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  // Review and draft come from the backend rules engine; overrides re-run it server-side.
  const [review, setReview] = useState<ReviewResult | null>(null);
  const [serverDraft, setServerDraft] = useState("");
  const [reviewing, setReviewing] = useState(false);
  const [runId, setRunId] = useState(0);
  const [completedAt, setCompletedAt] = useState(0);
  const [overrides, setOverrides] = useState<Overrides>({});
  const [expandedId, setExpandedId] = useState<string | null>(null);
  // null = draft follows the findings; a string = staff edited it by hand.
  const [draftEdit, setDraftEdit] = useState<string | null>(null);
  // Earlier analyses this session (in memory only), newest first, for the compare view.
  const [history, setHistory] = useState<CompareRun[]>([]);
  const [compareId, setCompareId] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const reviewSeq = useRef(0);

  // Elapsed-time ticker while analyzing (reset happens in analyze()).
  useEffect(() => {
    if (!analyzing) return;
    const t = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [analyzing]);

  const draft = draftEdit ?? serverDraft;
  const draftDirty = draftEdit !== null;

  const analyze = useCallback(async () => {
    if (!selection) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    // Snapshot the current analysis (with staff overrides) before replacing it.
    if (result && review) {
      const snapshot: CompareRun = { id: `run-${runId}`, name: result.file.name, completedAt, review };
      setHistory((h) => [snapshot, ...h].slice(0, HISTORY_LIMIT));
      setCompareId(snapshot.id);
    }

    setElapsed(0);
    setStage("uploading");
    setUploadPct(0);
    setAnalyzing(true);
    setError(null);
    setResult(null);
    setReview(null);
    setServerDraft("");
    setOverrides({});
    setExpandedId(null);
    setDraftEdit(null);

    try {
      const form = new FormData();
      if (selection.kind === "upload" && selection.file) form.append("file", selection.file);
      else if (selection.sample) form.append("sample", selection.sample);

      const body = await analyzePacket(form, controller.signal, (pct) => {
        setUploadPct(pct);
        if (pct === 100) setStage("analyzing");
      });
      setResult(body);
      setReview(body.review);
      setServerDraft(body.draft);
      setRunId((n) => n + 1);
      setCompletedAt(Date.now());
      setSelection((s) => (s ? { ...s, sizeBytes: body.file.sizeBytes } : s));
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      if (err instanceof ApiError) setError({ message: err.message, retryable: err.retryable });
      else setError({ message: "Could not reach the analysis API. Is the backend running on port 8000?", retryable: true });
    } finally {
      setAnalyzing(false);
      setUploadPct(null);
    }
  }, [selection, result, review, runId, completedAt]);

  async function applyOverride(id: string, override: ReviewerOverride | null) {
    if (!result) return;
    const next = { ...overrides };
    if (override) next[id] = override;
    else delete next[id];
    setOverrides(next);

    const seq = ++reviewSeq.current;
    setReviewing(true);
    try {
      const r = await reviewWithOverrides(result.file.name, result.extraction, next);
      if (seq !== reviewSeq.current) return; // a newer override request superseded this one
      setReview(r.review);
      setServerDraft(r.draft);
    } catch (err) {
      if (seq !== reviewSeq.current) return;
      setError({
        message: err instanceof ApiError ? err.message : "Could not re-run the checklist rules. Is the backend running?",
        retryable: true,
      });
    } finally {
      if (seq === reviewSeq.current) setReviewing(false);
    }
  }

  function jumpTo(id: string) {
    setExpandedId(id);
    requestAnimationFrame(() => {
      document.getElementById(`rule-${id}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  }

  function startOver() {
    abortRef.current?.abort();
    reviewSeq.current++;
    setSelection(null);
    setAnalyzing(false);
    setError(null);
    setResult(null);
    setReview(null);
    setServerDraft("");
    setReviewing(false);
    setOverrides({});
    setExpandedId(null);
    setDraftEdit(null);
    setHistory([]);
    setCompareId(null);
  }

  function exportSummary() {
    if (!result || !review) return;
    const payload = {
      exported_at: new Date().toISOString(),
      synthetic_demo: true,
      file: result.file,
      model: result.model,
      headline: review.headline,
      attention_count: review.attentionCount,
      items: review.items.map((i) => ({
        id: i.id,
        label: i.label,
        group: i.group,
        status: i.status,
        value: i.value,
        detail: i.detail,
        evidence: i.evidence,
        source: i.source,
        override: i.override,
      })),
      draft,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `intake-review-${result.file.name.replace(/\.pdf$/i, "")}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const phase: IntakePhase = analyzing
    ? "analyzing"
    : error
      ? "error"
      : result && selection && result.file.name === selection.name
        ? "done"
        : selection
          ? "ready"
          : "empty";

  const modelLine = result
    ? `Extraction: ${result.model.id} · ${(result.model.durationMs / 1000).toFixed(1)}s · ${result.model.usage.input_tokens.toLocaleString()} in / ${result.model.usage.output_tokens.toLocaleString()} out tokens · rules: deterministic checklist on the backend (docs/RULE_MAP.md)${reviewing ? " · re-checking…" : ""}`
    : "";
  const currentRun: CompareRun | null = result && review ? { id: `run-${runId}`, name: result.file.name, completedAt, review } : null;

  return (
    <div className="flex-1">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto max-w-6xl px-6 py-4 flex items-center justify-between gap-4">
          <div>
            <h1 className="text-lg font-semibold text-navy tracking-tight">Referral Intake Copilot</h1>
            <p className="text-xs text-slate-500">Review and prepare referral packets</p>
          </div>
          <div className="flex items-center gap-3">
            {(result || history.length > 0 || selection) && (
              <button type="button" onClick={startOver} className="text-xs font-medium text-slate-500 hover:text-slate-800 underline underline-offset-2">
                Start over
              </button>
            )}
            <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-[11px] font-semibold tracking-wide text-amber-900">
              <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
              DEMO · SYNTHETIC DATA
            </span>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-6 grid gap-5 lg:grid-cols-[340px_1fr] items-start">
        <div className="flex flex-col gap-5 lg:sticky lg:top-6">
          <IntakePanel
            selection={selection}
            onSelect={(s) => {
              setSelection(s);
              setError(null);
            }}
            phase={phase}
            stage={stage}
            uploadPct={uploadPct}
            elapsedSeconds={elapsed}
            onAnalyze={analyze}
            error={error}
            pages={phase === "done" ? (result?.file.pages ?? null) : null}
            durationMs={phase === "done" ? (result?.model.durationMs ?? null) : null}
          />
          {result && <SourcePanel extraction={result.extraction} fileUrl={result.file.url} />}
        </div>

        <div className="flex flex-col gap-5 min-w-0">
          {!result && !analyzing && (
            <section className="card p-8 text-center">
              <h2 className="text-base font-semibold text-navy">No packet analyzed yet</h2>
              <p className="mt-1 text-sm text-slate-600 max-w-md mx-auto">
                Choose a sample packet or upload a PDF, then click <span className="font-medium">Analyze packet</span>. Extracted fields,
                the documentation checklist, and a follow-up draft will appear here.
              </p>
              <ol className="mt-4 text-left text-xs text-slate-500 space-y-1 max-w-md mx-auto list-decimal list-inside">
                <li>The document model reads the PDF and extracts fields with page evidence.</li>
                <li>Deterministic checklist rules derived from the two reference forms decide what needs attention.</li>
                <li>Staff verify or correct findings; the summary and draft update immediately.</li>
                <li>Analyze a second packet to compare how the findings changed.</li>
              </ol>
              {history.length > 0 && (
                <p className="mt-4 text-xs text-slate-500">
                  {history.length} earlier analysis{history.length === 1 ? "" : "es"} kept in memory for comparison.
                </p>
              )}
            </section>
          )}

          {analyzing && (
            <section className="card p-8 text-center" role="status">
              {stage === "uploading" && uploadPct !== null ? (
                <>
                  <div className="h-1.5 rounded-full bg-slate-200 max-w-xs mx-auto overflow-hidden" aria-hidden>
                    <div className="h-full rounded-full bg-teal-600 transition-[width] duration-150" style={{ width: `${uploadPct}%` }} />
                  </div>
                  <p className="mt-4 text-sm text-slate-600">
                    Uploading {selection?.name}… {uploadPct}%
                  </p>
                </>
              ) : (
                <>
                  <div className="progress-indeterminate h-1.5 rounded-full max-w-xs mx-auto" aria-hidden />
                  <p className="mt-4 text-sm text-slate-600">
                    Analyzing {selection?.name}… {elapsed}s
                  </p>
                </>
              )}
              <p className="text-xs text-slate-400 mt-1">The model reads every page before any result is shown. Typically 20–60 seconds.</p>
            </section>
          )}

          {result && review && currentRun && (
            <>
              <SummaryCard review={review} modelLine={modelLine} onJump={jumpTo} />

              {history.length > 0 && <ComparePanel current={currentRun} previous={history} selectedId={compareId} onSelect={setCompareId} />}

              <div>
                <div className="flex items-baseline justify-between mb-2">
                  <h2 className="text-sm font-semibold text-navy">Documentation checklist</h2>
                  <span className="text-[11px] text-slate-500">Reference B, page 1: items the referring office must also fax</span>
                </div>
                <ChecklistGroup
                  group="documents"
                  items={review.items.filter((i) => i.group === "documents")}
                  expandedId={expandedId}
                  onToggle={(id) => setExpandedId((cur) => (cur === id ? null : id))}
                  onOverride={applyOverride}
                />
              </div>

              <div>
                <div className="flex items-baseline justify-between mb-2">
                  <h2 className="text-sm font-semibold text-navy">Extracted fields and evidence</h2>
                  <span className="text-[11px] text-slate-500">Click a row for evidence, source, and staff actions</span>
                </div>
                <div className="grid gap-4">
                  {FIELD_GROUPS.map((g) => (
                    <ChecklistGroup
                      key={g}
                      group={g}
                      items={review.items.filter((i) => i.group === g)}
                      expandedId={expandedId}
                      onToggle={(id) => setExpandedId((cur) => (cur === id ? null : id))}
                      onOverride={applyOverride}
                    />
                  ))}
                </div>
              </div>

              <DraftPanel
                draft={draft}
                dirty={draftDirty}
                attentionCount={review.attentionCount}
                onChange={(t) => setDraftEdit(t)}
                onRegenerate={() => setDraftEdit(null)}
                onExport={exportSummary}
              />
            </>
          )}
        </div>
      </main>

      <footer className="mx-auto max-w-6xl px-6 pb-6 text-[11px] text-slate-400">
        First-pass administrative intake assistant. Not a clinical, coverage, or eligibility decision. In-memory only; nothing is stored or sent.
      </footer>
    </div>
  );
}
