import type { Extraction } from "@/lib/types";

export default function SourcePanel({ extraction, fileUrl }: { extraction: Extraction; fileUrl: string | null }) {
  return (
    <section className="card p-5" aria-labelledby="source-heading">
      <div className="flex items-center justify-between gap-2">
        <h2 id="source-heading" className="text-sm font-semibold text-navy">
          Source document
        </h2>
        {fileUrl && (
          <a href={fileUrl} target="_blank" rel="noreferrer" className="text-xs font-medium text-teal-800 underline underline-offset-2">
            Open PDF
          </a>
        )}
      </div>
      <p className="text-xs text-slate-500 mt-0.5">Page references reported by the document model.</p>
      <ol className="mt-3 space-y-1.5">
        {extraction.page_summary.map((p) => (
          <li key={p.page} className="flex gap-2 text-xs">
            <span className="shrink-0 w-12 font-medium text-slate-500">Page {p.page}</span>
            <span className="text-slate-700">{p.description}</span>
          </li>
        ))}
        {extraction.page_summary.length === 0 && <li className="text-xs text-slate-400">No page summary returned.</li>}
      </ol>
      {extraction.packet_notes && (
        <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          <span className="font-semibold">Packet note: </span>
          {extraction.packet_notes}
        </div>
      )}
    </section>
  );
}
