"""AI extraction: sends the PDF to OpenAI and returns a schema-validated Extraction.

Flow: upload the PDF as a user_data file, ask the Responses API for output that
matches the Pydantic schema (Structured Outputs), then delete the uploaded file.
The PDF contents and the model output are never logged. Model output is treated
as untrusted data: strict validation first, lenient repair second.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Iterable

import openai
from pydantic import ValidationError

from .config import MODEL_ID, api_key_configured
from .prompt import SYSTEM_PROMPT, USER_INSTRUCTION
from .schema import DOCUMENT_IDS, FIELD_IDS, STATUSES, Extraction, normalize_extraction

ErrorCode = str  # missing_api_key | auth | rate_limit | bad_request | api | network | refusal | truncated | invalid_output

MAX_OUTPUT_TOKENS = 16000


class ExtractionError(Exception):
    def __init__(self, message: str, code: ErrorCode, retryable: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True)
class ExtractionRun:
    extraction: Extraction
    model: str
    usage: dict[str, int]
    duration_ms: int


def _map_api_error(err: openai.OpenAIError) -> ExtractionError:
    if isinstance(err, openai.AuthenticationError):
        return ExtractionError("The OpenAI API rejected the API key.", "auth")
    if isinstance(err, openai.RateLimitError):
        return ExtractionError("The model API is rate limited. Try again in a moment.", "rate_limit", True)
    if isinstance(err, openai.BadRequestError):
        return ExtractionError(f"The model API rejected the request: {err.message}", "bad_request")
    if isinstance(err, openai.APIConnectionError):
        return ExtractionError("Could not reach the model API. Check network access.", "network", True)
    if isinstance(err, openai.APIStatusError):
        status = getattr(err, "status_code", 0) or 0
        return ExtractionError(f"Model API error {status}: {err.message}", "api", status >= 500)
    return ExtractionError(f"Unexpected error during extraction: {err}", "api", True)


def extract_from_pdf(pdf_bytes: bytes, file_name: str = "packet.pdf") -> ExtractionRun:
    if not api_key_configured():
        raise ExtractionError(
            "OPENAI_API_KEY is not set. Copy backend/.env.example to backend/.env and add a key, then restart the server.",
            "missing_api_key",
        )

    client = openai.OpenAI()
    started = time.monotonic()
    uploaded_id: str | None = None
    try:
        try:
            uploaded = client.files.create(
                file=(file_name, BytesIO(pdf_bytes), "application/pdf"),
                purpose="user_data",
            )
            uploaded_id = uploaded.id
            response = client.responses.parse(
                model=MODEL_ID,
                instructions=SYSTEM_PROMPT,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_file", "file_id": uploaded_id},
                            {"type": "input_text", "text": USER_INSTRUCTION},
                        ],
                    }
                ],
                text_format=Extraction,
                max_output_tokens=MAX_OUTPUT_TOKENS,
            )
        except openai.OpenAIError as err:
            raise _map_api_error(err) from err
    finally:
        if uploaded_id:
            _delete_quietly(client, uploaded_id)
    duration_ms = int((time.monotonic() - started) * 1000)

    if _has_refusal(response):
        raise ExtractionError("The model declined to process this document. No results were produced.", "refusal")
    incomplete = getattr(response, "incomplete_details", None)
    if getattr(response, "status", None) == "incomplete" and getattr(incomplete, "reason", None) == "max_output_tokens":
        raise ExtractionError(
            "The model output was cut off before completion. No results were produced.", "truncated", True
        )

    candidate = response.output_parsed or parse_output(_output_texts(response))
    if candidate is None:
        raise ExtractionError(
            "The model returned output that did not match the expected schema.", "invalid_output", True
        )

    usage = getattr(response, "usage", None)
    return ExtractionRun(
        extraction=normalize_extraction(candidate),
        model=getattr(response, "model", None) or MODEL_ID,
        usage={
            "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
            "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
        },
        duration_ms=duration_ms,
    )


def _delete_quietly(client: openai.OpenAI, file_id: str) -> None:
    """Remove the uploaded packet from OpenAI storage once the request is finished."""
    try:
        client.files.delete(file_id)
    except openai.OpenAIError:
        pass  # cleanup failure must not hide the analysis result; the file expires per account policy


# ---------------------------------------------------------------------------
# Output handling: strict first, lenient repair second
# ---------------------------------------------------------------------------


def _has_refusal(response: Any) -> bool:
    for item in getattr(response, "output", None) or []:
        for part in getattr(item, "content", None) or []:
            if getattr(part, "type", None) == "refusal":
                return True
    return False


def _output_texts(response: Any) -> list[str]:
    text = getattr(response, "output_text", None)
    if isinstance(text, str) and text:
        return [text]
    out: list[str] = []
    for item in getattr(response, "output", None) or []:
        for part in getattr(item, "content", None) or []:
            if getattr(part, "type", None) == "output_text" and isinstance(getattr(part, "text", None), str):
                out.append(part.text)
    return out


def parse_output(texts: Iterable[str]) -> Extraction | None:
    """Strict schema validation of the model text; falls back to lenient repair."""
    texts = [t for t in texts if t]
    if not texts:
        return None
    text = texts[0]
    try:
        return Extraction.model_validate_json(text)
    except ValidationError:
        return lenient_parse(text)


def _nullable_str(v: Any) -> str | None:
    return v if isinstance(v, str) else None


def _nullable_int(v: Any) -> int | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return None


def _status(v: Any) -> str:
    return v if isinstance(v, str) and v in STATUSES else "uncertain"


def lenient_parse(text: str) -> Extraction | None:
    """Parse the raw model text, drop records with unknown ids, coerce unknown statuses to
    "uncertain", and validate. Returns None when the text is not usable JSON at all."""
    try:
        raw = json.loads(text)
    except ValueError:
        return None
    if not isinstance(raw, dict):
        return None

    fields: list[dict[str, Any]] = []
    for f in raw.get("fields") or []:
        if not isinstance(f, dict) or f.get("field") not in FIELD_IDS:
            continue
        ev = f.get("evidence") if isinstance(f.get("evidence"), dict) else {}
        st = _status(f.get("status"))
        note = _nullable_str(f.get("note"))
        if note is None and st != f.get("status"):
            note = "Extraction reported an unrecognized status."
        fields.append(
            {
                "field": f["field"],
                "status": st,
                "value": _nullable_str(f.get("value")),
                "evidence": {"page": _nullable_int(ev.get("page")), "excerpt": _nullable_str(ev.get("excerpt"))},
                "note": note,
            }
        )

    documents: list[dict[str, Any]] = []
    for d in raw.get("documents") or []:
        if not isinstance(d, dict) or d.get("category") not in DOCUMENT_IDS:
            continue
        pages_raw = d.get("pages") if isinstance(d.get("pages"), list) else []
        pages = [p for p in (_nullable_int(x) for x in pages_raw) if p is not None]
        documents.append(
            {
                "category": d["category"],
                "status": _status(d.get("status")),
                "pages": pages,
                "excerpt": _nullable_str(d.get("excerpt")),
                "note": _nullable_str(d.get("note")),
            }
        )

    page_summary: list[dict[str, Any]] = []
    for p in raw.get("page_summary") or []:
        if isinstance(p, dict) and _nullable_int(p.get("page")) is not None and isinstance(p.get("description"), str):
            page_summary.append({"page": _nullable_int(p["page"]), "description": p["description"]})

    try:
        return Extraction.model_validate(
            {
                "fields": fields,
                "documents": documents,
                "page_summary": page_summary,
                "packet_notes": _nullable_str(raw.get("packet_notes")),
            }
        )
    except ValidationError:
        return None
