"""FastAPI application: analysis, deterministic review, samples, rule map.

Run from backend/:  uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from .config import ALLOWED_ORIGINS, MAX_PAGES, MAX_UPLOAD_BYTES, MODEL_ID, api_key_configured
from .draft import build_draft
from .extract import ExtractionError, extract_from_pdf
from .pdfutil import count_pages, looks_like_pdf
from .rules import CamelModel, ReviewResult, ReviewerOverride, evaluate, rule_map
from .samples import SAMPLES, list_samples, sample_path, sample_url
from .schema import Extraction

log = logging.getLogger("referral_intake")

app = FastAPI(title="Referral Intake Copilot API", version="0.2.0", docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Response models (camelCase on the wire; the frontend types mirror these)
# ---------------------------------------------------------------------------


class FileInfo(CamelModel):
    name: str
    size_bytes: int
    pages: int | None
    synthetic: bool
    url: str | None


class ModelInfo(CamelModel):
    id: str
    usage: dict[str, int]
    duration_ms: int


class AnalyzeResponse(CamelModel):
    file: FileInfo
    extraction: Extraction
    review: ReviewResult
    draft: str
    model: ModelInfo


class ReviewRequest(BaseModel):
    file_name: str = "packet.pdf"
    extraction: Extraction
    overrides: dict[str, ReviewerOverride] = Field(default_factory=dict)


class ReviewResponse(CamelModel):
    review: ReviewResult
    draft: str


class ApiError(BaseModel):
    error: str
    code: str
    retryable: bool = False


def _error(status: int, message: str, code: str, retryable: bool = False) -> JSONResponse:
    return JSONResponse(status_code=status, content=ApiError(error=message, code=code, retryable=retryable).model_dump())


@app.exception_handler(RequestValidationError)
async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    first = exc.errors()[0] if exc.errors() else {}
    loc = ".".join(str(p) for p in first.get("loc", []) if p not in ("body",))
    msg = first.get("msg", "Invalid request.")
    return _error(400, f"Invalid request{f' at {loc}' if loc else ''}: {msg}", "bad_request")


@app.exception_handler(ExtractionError)
async def _extraction_error(_: Request, exc: ExtractionError) -> JSONResponse:
    status = 400 if exc.code == "bad_request" else 500 if exc.code in ("missing_api_key", "auth") else 502
    log.error("[analyze] %s: %s", exc.code, exc.message)  # message only; never the document
    return _error(status, exc.message, exc.code, exc.retryable)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/api/health")
def health() -> dict[str, object]:
    return {"ok": True, "model": MODEL_ID, "apiKeyConfigured": api_key_configured(), "samples": list_samples()}


@app.get("/api/samples")
def samples() -> list[dict[str, object]]:
    return list_samples()


@app.get("/api/samples/{key}/file")
def sample_file(key: str):
    if key not in SAMPLES:
        return _error(404, f'Unknown sample "{key}".', "not_found")
    path = sample_path(key)
    if not path.is_file():
        return _error(404, f"Sample {path.name} is not present. Run: python scripts/generate_samples.py", "not_found")
    return FileResponse(path, media_type="application/pdf", filename=path.name, content_disposition_type="inline")


@app.get("/api/rules")
def rules() -> list[dict]:
    return rule_map()


def _read_input(file: UploadFile | None, sample: str | None) -> tuple[str, bytes, bool, str | None]:
    if sample is not None:
        if sample not in SAMPLES:
            raise ExtractionError(f'Unknown sample "{sample}".', "bad_request")
        path = sample_path(sample)
        if not path.is_file():
            raise ExtractionError(
                f'Sample "{path.name}" is not present. Run: python scripts/generate_samples.py', "bad_request"
            )
        return path.name, path.read_bytes(), True, sample_url(sample)

    if file is None:
        raise ExtractionError("No PDF file was provided.", "bad_request")
    name = file.filename or "upload.pdf"
    is_pdf = (file.content_type == "application/pdf") or name.lower().endswith(".pdf")
    if not is_pdf:
        raise ExtractionError("Only PDF files are supported.", "bad_request")
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if not data:
        raise ExtractionError("The uploaded file is empty.", "bad_request")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ExtractionError("The PDF is larger than 20 MB.", "bad_request")
    return name, data, False, None


@app.post("/api/analyze", response_model=AnalyzeResponse, responses={400: {"model": ApiError}, 500: {"model": ApiError}, 502: {"model": ApiError}})
def analyze(file: UploadFile | None = File(default=None), sample: str | None = Form(default=None)):
    """Analyze one packet: multipart with either `file` (a PDF) or `sample` (complete | incomplete | ambiguous).

    Runs synchronously in FastAPI's threadpool because the model call blocks for tens of seconds.
    """
    name, data, synthetic, url = _read_input(file, sample)

    if not looks_like_pdf(data):
        raise ExtractionError("The file does not look like a PDF.", "bad_request")
    pages = count_pages(data)
    if pages is not None and pages > MAX_PAGES:
        raise ExtractionError(f"The PDF has {pages} pages; the demo accepts up to {MAX_PAGES}.", "bad_request")

    run = extract_from_pdf(data, name)
    review = evaluate(run.extraction)
    draft = build_draft(review, run.extraction, name)

    return AnalyzeResponse(
        file=FileInfo(name=name, size_bytes=len(data), pages=pages, synthetic=synthetic, url=url),
        extraction=run.extraction,
        review=review,
        draft=draft,
        model=ModelInfo(id=run.model, usage=run.usage, duration_ms=run.duration_ms),
    )


@app.post("/api/review", response_model=ReviewResponse)
def review(body: ReviewRequest) -> ReviewResponse:
    """Re-run the deterministic rules with staff overrides. No model call."""
    result = evaluate(body.extraction, body.overrides)
    return ReviewResponse(review=result, draft=build_draft(result, body.extraction, body.file_name))
