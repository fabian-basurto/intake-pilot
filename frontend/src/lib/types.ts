/**
 * Wire types mirrored from the FastAPI backend (backend/app/schema.py, rules.py, main.py).
 * Extraction records use snake_case; review/response envelopes use camelCase.
 */

// --- Extraction (AI layer output) ------------------------------------------

export type ExtractionStatus = "found" | "not_found" | "uncertain";

export interface Evidence {
  page: number | null;
  excerpt: string | null;
}

export interface ExtractedField {
  field: string;
  status: ExtractionStatus;
  value: string | null;
  evidence: Evidence;
  note: string | null;
}

export interface ExtractedDocument {
  category: string;
  status: ExtractionStatus;
  pages: number[];
  excerpt: string | null;
  note: string | null;
}

export interface PageSummary {
  page: number;
  description: string;
}

export interface Extraction {
  fields: ExtractedField[];
  documents: ExtractedDocument[];
  page_summary: PageSummary[];
  packet_notes: string | null;
}

// --- Review (rules layer output) -------------------------------------------

export type RuleGroup = "documents" | "patient" | "insurance" | "order" | "contact";
export type RuleLevel = "required" | "info";
export type RuleStatus = "ok" | "not_found" | "needs_review" | "info";

export interface RuleSource {
  pdf: "A" | "B";
  page: number;
  section: string;
}

export interface ReviewerOverride {
  kind: "verified" | "corrected";
  value?: string | null;
  note?: string | null;
}
export type Overrides = Record<string, ReviewerOverride>;

export interface RuleResult {
  id: string;
  label: string;
  group: RuleGroup;
  level: RuleLevel;
  status: RuleStatus;
  detail: string;
  value: string | null;
  evidence: Evidence | null;
  source: RuleSource[];
  request: string;
  override: ReviewerOverride | null;
  fieldRecords: ExtractedField[];
  documentRecords: ExtractedDocument[];
}

export interface ReviewResult {
  status: "clear" | "attention";
  headline: string;
  subline: string;
  attentionCount: number;
  counts: Record<RuleStatus, number>;
  items: RuleResult[];
}

export const GROUP_LABELS: Record<RuleGroup, string> = {
  documents: "Supporting documents",
  patient: "Patient demographics",
  insurance: "Insurance",
  order: "ENTYVIO order",
  contact: "Referring office contact",
};

export const SOURCE_LABELS: Record<RuleSource["pdf"], string> = {
  A: "Reference A — ENTYVIO infusion order form",
  B: "Reference B — Referral Checklist",
};

// --- Samples -----------------------------------------------------------------

export type SampleKey = "complete" | "incomplete" | "ambiguous";

export const SAMPLES: Record<SampleKey, { file: string; label: string; description: string }> = {
  complete: { file: "packet_complete.pdf", label: "Complete packet", description: "All checklist categories present" },
  incomplete: { file: "packet_incomplete.pdf", label: "Missing documentation", description: "Two categories omitted" },
  ambiguous: { file: "packet_ambiguous.pdf", label: "Ambiguous packet", description: "One conflicting order field" },
};

// --- API envelopes -----------------------------------------------------------

export interface AnalyzeResponse {
  file: { name: string; sizeBytes: number; pages: number | null; synthetic: boolean; url: string | null };
  extraction: Extraction;
  review: ReviewResult;
  draft: string;
  model: { id: string; usage: { input_tokens: number; output_tokens: number }; durationMs: number };
}

export interface ReviewResponse {
  review: ReviewResult;
  draft: string;
}

export interface AnalyzeErrorResponse {
  error: string;
  code: string;
  retryable: boolean;
}
