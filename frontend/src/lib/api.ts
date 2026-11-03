import type { AnalyzeErrorResponse, AnalyzeResponse, Extraction, Overrides, ReviewResponse } from "./types";

/**
 * Thin client for the FastAPI backend. Requests go to same-origin /api/*, which
 * next.config.ts rewrites to the backend, so no CORS setup is needed in the browser.
 */

export interface PostResult<T> {
  ok: boolean;
  status: number;
  body: T | AnalyzeErrorResponse | null;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code: string,
    public readonly retryable: boolean,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** POST a form with upload progress. fetch() cannot report upload progress, so this uses XMLHttpRequest. */
export function postForm<T>(url: string, form: FormData, signal: AbortSignal, onProgress: (pct: number | null) => void): Promise<PostResult<T>> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    xhr.responseType = "json";
    xhr.upload.onprogress = (e) => onProgress(e.lengthComputable ? Math.min(100, Math.round((e.loaded / e.total) * 100)) : null);
    xhr.upload.onload = () => onProgress(100);
    xhr.onload = () => resolve({ ok: xhr.status >= 200 && xhr.status < 300, status: xhr.status, body: xhr.response });
    xhr.onerror = () => reject(new Error("network"));
    xhr.onabort = () => reject(Object.assign(new Error("aborted"), { name: "AbortError" }));
    signal.addEventListener("abort", () => xhr.abort(), { once: true });
    xhr.send(form);
  });
}

export function isErrorBody(body: unknown): body is AnalyzeErrorResponse {
  return !!body && typeof body === "object" && "error" in body;
}

export async function analyzePacket(form: FormData, signal: AbortSignal, onProgress: (pct: number | null) => void): Promise<AnalyzeResponse> {
  const res = await postForm<AnalyzeResponse>("/api/analyze", form, signal, onProgress);
  if (!res.ok || !res.body || isErrorBody(res.body)) {
    const e = isErrorBody(res.body) ? res.body : { error: `Server returned ${res.status}.`, code: "http", retryable: res.status >= 500 };
    throw new ApiError(e.error, res.status, e.code, !!e.retryable);
  }
  return res.body;
}

/** Re-run the deterministic checklist with staff overrides. No model call; typically a few milliseconds. */
export async function reviewWithOverrides(fileName: string, extraction: Extraction, overrides: Overrides, signal?: AbortSignal): Promise<ReviewResponse> {
  const res = await fetch("/api/review", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ file_name: fileName, extraction, overrides }),
    signal,
  });
  const body = (await res.json().catch(() => null)) as ReviewResponse | AnalyzeErrorResponse | null;
  if (!res.ok || !body || isErrorBody(body)) {
    const e = isErrorBody(body) ? body : { error: `Server returned ${res.status}.`, code: "http", retryable: res.status >= 500 };
    throw new ApiError(e.error, res.status, e.code, !!e.retryable);
  }
  return body;
}
