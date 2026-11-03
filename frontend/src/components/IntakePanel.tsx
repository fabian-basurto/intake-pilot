"use client";

import { useRef } from "react";
import { SAMPLES, type SampleKey } from "@/lib/types";

export interface IntakeSelection {
  kind: "upload" | "sample";
  file?: File;
  sample?: SampleKey;
  name: string;
  sizeBytes: number | null;
}

export type IntakePhase = "empty" | "ready" | "analyzing" | "done" | "error";
export type AnalyzeStage = "uploading" | "analyzing";

interface Props {
  selection: IntakeSelection | null;
  onSelect: (s: IntakeSelection | null) => void;
  phase: IntakePhase;
  stage: AnalyzeStage;
  uploadPct: number | null;
  elapsedSeconds: number;
  onAnalyze: () => void;
  error: { message: string; retryable: boolean } | null;
  pages: number | null;
  durationMs: number | null;
}

export function formatBytes(n: number | null) {
  if (n === null) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export default function IntakePanel({ selection, onSelect, phase, stage, uploadPct, elapsedSeconds, onAnalyze, error, pages, durationMs }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const analyzing = phase === "analyzing";
  const attached = selection?.kind === "upload";

  function pickFile(file: File | undefined) {
    if (!file || analyzing) return;
    onSelect({ kind: "upload", file, name: file.name, sizeBytes: file.size });
  }

  function openDialog() {
    if (!analyzing) inputRef.current?.click();
  }

  const dragProps = {
    onDragOver: (e: React.DragEvent) => e.preventDefault(),
    onDrop: (e: React.DragEvent) => {
      e.preventDefault();
      pickFile(e.dataTransfer.files?.[0]);
    },
  };

  return (
    <section className="card p-5 flex flex-col gap-4" aria-labelledby="intake-heading">
      <div>
        <h2 id="intake-heading" className="text-sm font-semibold text-navy">
          Referral packet
        </h2>
        <p className="text-xs text-slate-500 mt-0.5">Upload one combined PDF, or choose a sample packet.</p>
      </div>

      <Stepper phase={phase} />

      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,.pdf"
        className="sr-only"
        disabled={analyzing}
        onChange={(e) => {
          pickFile(e.target.files?.[0]);
          e.target.value = ""; // allow re-selecting the same file after Remove
        }}
      />

      {attached && selection ? (
        <div
          {...dragProps}
          className={`rounded-lg border px-4 py-3 ${analyzing ? "border-slate-200 opacity-80" : "border-teal-500 bg-teal-50/40"}`}
          aria-live="polite"
        >
          <div className="flex items-start gap-3">
            <span className="mt-0.5 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-teal-600 text-white text-xs font-bold" aria-hidden>
              PDF
            </span>
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium text-slate-800 truncate" title={selection.name}>
                {selection.name}
              </div>
              <div className="text-xs text-teal-800">
                Attached · {formatBytes(selection.sizeBytes)}
                {pages !== null && phase === "done" ? ` · ${pages} page${pages === 1 ? "" : "s"}` : ""}
              </div>
            </div>
          </div>
          {!analyzing && (
            <div className="mt-2 flex gap-3 text-xs">
              <button type="button" onClick={openDialog} className="font-medium text-teal-800 underline underline-offset-2 hover:text-teal-900">
                Change file
              </button>
              <button type="button" onClick={() => onSelect(null)} className="font-medium text-slate-500 underline underline-offset-2 hover:text-slate-800">
                Remove
              </button>
            </div>
          )}
        </div>
      ) : (
        <button
          type="button"
          onClick={openDialog}
          disabled={analyzing}
          {...dragProps}
          className={`block w-full rounded-lg border border-dashed px-4 py-5 text-center transition-colors ${
            analyzing ? "opacity-60 cursor-not-allowed border-slate-200" : "border-slate-300 hover:border-teal-500 hover:bg-teal-50/40 cursor-pointer"
          }`}
        >
          <div className="text-sm font-medium text-slate-700">Upload PDF</div>
          <div className="text-xs text-slate-500 mt-1">Drag and drop or click to browse · PDF only · up to 20 MB</div>
        </button>
      )}

      <div>
        <div className="text-xs font-medium text-slate-500 mb-2">Sample packets (synthetic)</div>
        <div className="grid grid-cols-1 gap-2">
          {(Object.keys(SAMPLES) as SampleKey[]).map((key) => {
            const s = SAMPLES[key];
            const active = selection?.kind === "sample" && selection.sample === key;
            return (
              <button
                key={key}
                type="button"
                disabled={analyzing}
                onClick={() => onSelect({ kind: "sample", sample: key, name: s.file, sizeBytes: null })}
                className={`text-left rounded-md border px-3 py-2 transition-colors disabled:opacity-60 ${
                  active ? "border-teal-600 bg-teal-50/60" : "border-slate-200 hover:border-slate-300 hover:bg-slate-50"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="text-sm font-medium text-slate-800">{s.label}</div>
                  {active && <span className="text-[11px] font-medium text-teal-800">Selected</span>}
                </div>
                <div className="text-xs text-slate-500">{s.description}</div>
              </button>
            );
          })}
        </div>
      </div>

      <div className="rounded-md bg-slate-50 border border-slate-200 px-3 py-2.5 text-xs" aria-live="polite">
        <div className="flex items-center justify-between gap-2">
          <span className="font-medium text-slate-600">Packet status</span>
          <StatusBadge phase={phase} stage={stage} uploadPct={uploadPct} elapsed={elapsedSeconds} pages={pages} />
        </div>
        {selection ? (
          <dl className="mt-1.5 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-slate-700">
            <dt className="text-slate-500">Name</dt>
            <dd className="truncate" title={selection.name}>
              {selection.name}
            </dd>
            <dt className="text-slate-500">Source</dt>
            <dd>{selection.kind === "upload" ? "Uploaded by you" : "Built-in sample"}</dd>
            <dt className="text-slate-500">Size</dt>
            <dd>{formatBytes(selection.sizeBytes)}</dd>
            <dt className="text-slate-500">Pages</dt>
            <dd>{pages ?? (phase === "done" ? "unknown" : "counted during analysis")}</dd>
            {phase === "done" && durationMs !== null && (
              <>
                <dt className="text-slate-500">Analysis</dt>
                <dd>{(durationMs / 1000).toFixed(1)}s</dd>
              </>
            )}
          </dl>
        ) : (
          <p className="mt-1.5 text-slate-500">No packet selected. Upload a PDF or pick a sample.</p>
        )}
        <div className="mt-2 inline-flex items-center rounded-full bg-amber-100 text-amber-900 px-2 py-0.5 text-[10px] font-semibold tracking-wide">
          SYNTHETIC DEMO DATA ONLY
        </div>
      </div>

      <button
        type="button"
        onClick={onAnalyze}
        disabled={!selection || analyzing}
        className="w-full rounded-md bg-navy text-white text-sm font-semibold py-2.5 hover:bg-navy-soft disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {analyzing ? (stage === "uploading" ? "Uploading packet…" : "Analyzing packet…") : phase === "done" ? "Analyze again" : "Analyze packet"}
      </button>

      {analyzing && (
        <div className="text-xs text-slate-600" role="status">
          {stage === "uploading" && uploadPct !== null ? (
            <>
              <div className="h-1.5 rounded-full bg-slate-200 mb-2 overflow-hidden" aria-hidden>
                <div className="h-full rounded-full bg-teal-600 transition-[width] duration-150" style={{ width: `${uploadPct}%` }} />
              </div>
              Uploading packet to the server · {uploadPct}%
            </>
          ) : (
            <>
              <div className="progress-indeterminate h-1.5 rounded-full mb-2" aria-hidden />
              Upload complete. Reading the packet with the document model and applying checklist rules · {elapsedSeconds}s
            </>
          )}
        </div>
      )}

      {error && (
        <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2.5 text-xs text-red-800">
          <div className="font-semibold">Analysis failed. No results were produced.</div>
          <div className="mt-0.5">{error.message}</div>
          {error.retryable && <div className="mt-1 text-red-700">This may be temporary. Try again.</div>}
        </div>
      )}
    </section>
  );
}

function Stepper({ phase }: { phase: IntakePhase }) {
  const steps = [
    { label: "Attach", state: phase === "empty" ? "current" : "done" },
    { label: "Analyze", state: phase === "analyzing" ? "current" : phase === "done" ? "done" : phase === "error" ? "error" : "todo" },
    { label: "Review", state: phase === "done" ? "current" : "todo" },
  ] as const;
  return (
    <ol className="flex items-center gap-2 text-[11px]" aria-label="Progress">
      {steps.map((s, i) => (
        <li key={s.label} className="flex items-center gap-2">
          <span
            className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 font-medium ${
              s.state === "done"
                ? "border-teal-200 bg-teal-50 text-teal-800"
                : s.state === "current"
                  ? "border-navy bg-navy text-white"
                  : s.state === "error"
                    ? "border-red-200 bg-red-50 text-red-800"
                    : "border-slate-200 bg-white text-slate-400"
            }`}
          >
            <span className="inline-flex h-3.5 w-3.5 items-center justify-center rounded-full bg-white/20 text-[9px]">{s.state === "done" ? "✓" : i + 1}</span>
            {s.label}
          </span>
          {i < steps.length - 1 && <span className="h-px w-4 bg-slate-200" aria-hidden />}
        </li>
      ))}
    </ol>
  );
}

function StatusBadge({ phase, stage, uploadPct, elapsed, pages }: { phase: IntakePhase; stage: AnalyzeStage; uploadPct: number | null; elapsed: number; pages: number | null }) {
  const map: Record<IntakePhase, { text: string; cls: string }> = {
    empty: { text: "Nothing attached", cls: "border-slate-200 bg-white text-slate-500" },
    ready: { text: "Attached · ready to analyze", cls: "border-teal-200 bg-teal-50 text-teal-800" },
    analyzing: {
      text: stage === "uploading" && uploadPct !== null ? `Uploading · ${uploadPct}%` : `Analyzing · ${elapsed}s`,
      cls: "border-navy bg-navy text-white",
    },
    done: { text: `Analyzed${pages !== null ? ` · ${pages} page${pages === 1 ? "" : "s"}` : ""}`, cls: "border-teal-200 bg-teal-50 text-teal-800" },
    error: { text: "Failed", cls: "border-red-200 bg-red-50 text-red-800" },
  };
  // Fallback guards against a half-applied hot reload where the parent has not passed `phase` yet.
  const m = map[phase] ?? map.empty;
  return <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${m.cls}`}>{m.text}</span>;
}
