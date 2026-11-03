"""Offline checks of model-output handling and the extractor's control flow.

The OpenAI client is replaced with a fake, so no API call and no key are needed.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import openai
import pytest

from app.extract import ExtractionError, extract_from_pdf, lenient_parse, parse_output
from app.rules import evaluate
from app.schema import DOCUMENT_IDS, FIELD_IDS, Extraction, normalize_extraction
from tests.conftest import _full_extraction

try:
    import httpx2 as httpx_mod  # openai may be built on httpx2 in current releases
except ImportError:  # pragma: no cover
    import httpx as httpx_mod


def text(s: str) -> str:
    return s


# --- lenient repair ------------------------------------------------------------


def test_non_json_is_none():
    assert lenient_parse("not json") is None
    assert lenient_parse("[1, 2]") is None


def test_lenient_parse_repairs_messy_output():
    raw = {
        "fields": [
            {"field": "patient_name", "status": "found", "value": "Jordan Q. Testpatient", "evidence": {"page": 1, "excerpt": "Patient Name Jordan"}, "note": None},
            {"field": "made_up_field", "status": "found", "value": "x", "evidence": {"page": 1, "excerpt": None}, "note": None},
            {"field": "icd10_code", "status": "present", "value": "K51.90", "evidence": {"page": "2", "excerpt": None}, "note": None},
            {"field": "patient_dob", "status": "not_found", "value": 12, "evidence": None, "note": None},
            "garbage",
        ],
        "documents": [
            {"category": "recent_labs", "status": "found", "pages": [4, "x", 4.5, 5.0], "excerpt": "Laboratory Results", "note": None},
            {"category": "unknown_doc", "status": "found", "pages": [1], "excerpt": None, "note": None},
        ],
        "page_summary": [{"page": 1, "description": "cover"}, {"page": "2", "description": "order"}, {"page": 3}],
        "packet_notes": 42,
    }
    parsed = lenient_parse(json.dumps(raw))
    assert isinstance(parsed, Extraction)

    by_id = {f.field: f for f in parsed.fields}
    assert "made_up_field" not in by_id
    assert len(parsed.fields) == 3
    assert by_id["icd10_code"].status == "uncertain"
    assert by_id["icd10_code"].note == "Extraction reported an unrecognized status."
    assert by_id["icd10_code"].evidence.page is None
    assert by_id["patient_dob"].value is None
    assert by_id["patient_dob"].evidence.page is None and by_id["patient_dob"].evidence.excerpt is None

    docs = {d.category: d for d in parsed.documents}
    assert list(docs) == ["recent_labs"]
    assert docs["recent_labs"].pages == [4, 5]
    assert len(parsed.page_summary) == 1
    assert parsed.packet_notes is None

    norm = normalize_extraction(parsed)
    assert len(norm.fields) == len(FIELD_IDS)
    assert len(norm.documents) == len(DOCUMENT_IDS)
    assert next(f for f in norm.fields if f.field == "provider_fax").status == "not_found"

    review = evaluate(norm)
    assert review.attention_count > 0
    assert next(i for i in review.items if i.id == "icd10_code").status == "needs_review"


def test_parse_output_prefers_strict_then_repairs():
    good = _full_extraction().model_dump()
    assert parse_output([json.dumps(good)]) == _full_extraction()
    bad = dict(good, fields=good["fields"] + [{"field": "nope", "status": "found", "value": None, "evidence": {"page": None, "excerpt": None}, "note": None}])
    repaired = parse_output([json.dumps(bad)])
    assert repaired is not None and len(repaired.fields) == len(FIELD_IDS)
    assert parse_output(["garbage"]) is None
    assert parse_output([]) is None


def test_strict_schema_rejects_unknown_id():
    bad = {"fields": [{"field": "nope", "status": "found", "value": None, "evidence": {"page": None, "excerpt": None}, "note": None}], "documents": [], "page_summary": [], "packet_notes": None}
    with pytest.raises(Exception):
        Extraction.model_validate(bad)


# --- extractor control flow with a fake client --------------------------------


def fake_response(body: str | None, status: str = "completed", parsed=None, refusal: bool = False):
    content = []
    if refusal:
        content.append(SimpleNamespace(type="refusal", refusal="I can't help with that."))
    elif body is not None:
        content.append(SimpleNamespace(type="output_text", text=body))
    return SimpleNamespace(
        status=status,
        incomplete_details=None,
        output=[SimpleNamespace(type="message", content=content)],
        output_text=body or "",
        output_parsed=parsed,
        model="fake-model",
        usage=SimpleNamespace(input_tokens=11, output_tokens=7),
    )


class FakeFiles:
    def __init__(self, error: Exception | None = None) -> None:
        self.created: dict = {}
        self.deleted: list[str] = []
        self.error = error

    def create(self, **kwargs):
        if self.error:
            raise self.error
        self.created = kwargs
        return SimpleNamespace(id="file_test123")

    def delete(self, file_id: str):
        self.deleted.append(file_id)
        return SimpleNamespace(id=file_id, deleted=True)


class FakeResponses:
    def __init__(self, response=None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.kwargs: dict = {}

    def parse(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return self.response


class FakeOpenAI:
    def __init__(self, files: FakeFiles, responses: FakeResponses) -> None:
        self.files = files
        self.responses = responses


def install(monkeypatch, responses: FakeResponses, files: FakeFiles | None = None) -> FakeFiles:
    files = files or FakeFiles()
    monkeypatch.setattr("app.extract.openai.OpenAI", lambda: FakeOpenAI(files, responses))
    return files


@pytest.fixture
def with_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")


def test_missing_api_key_fails_visibly(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ExtractionError) as info:
        extract_from_pdf(b"%PDF-1.4 fake")
    assert info.value.code == "missing_api_key"
    assert "OPENAI_API_KEY" in info.value.message
    assert info.value.retryable is False


def test_extract_uploads_pdf_requests_schema_and_deletes_file(monkeypatch, with_key):
    expected = _full_extraction()
    responses = FakeResponses(fake_response(expected.model_dump_json(), parsed=expected))
    files = install(monkeypatch, responses)

    run = extract_from_pdf(b"%PDF-1.4 synthetic", "packet_test.pdf")

    assert run.extraction == expected
    assert run.model == "fake-model"
    assert run.usage == {"input_tokens": 11, "output_tokens": 7}

    upload = files.created
    assert upload["purpose"] == "user_data"
    name, handle, mime = upload["file"]
    assert name == "packet_test.pdf" and mime == "application/pdf"
    assert handle.read() == b"%PDF-1.4 synthetic"

    kw = responses.kwargs
    assert kw["text_format"] is Extraction
    assert kw["model"] == "gpt-4.1"
    assert kw["max_output_tokens"] == 16000
    assert "never guess" in kw["instructions"].lower()
    content = kw["input"][0]["content"]
    assert content[0] == {"type": "input_file", "file_id": "file_test123"}
    assert content[1]["type"] == "input_text"

    assert files.deleted == ["file_test123"]  # the packet is removed from OpenAI storage


def test_extract_repairs_schema_invalid_output(monkeypatch, with_key):
    good = _full_extraction().model_dump()
    bad = dict(good, fields=good["fields"] + [{"field": "hallucinated", "status": "maybe", "value": "x", "evidence": {"page": 9, "excerpt": None}, "note": None}])
    install(monkeypatch, FakeResponses(fake_response(json.dumps(bad), parsed=None)))
    run = extract_from_pdf(b"%PDF-1.4")
    assert len(run.extraction.fields) == len(FIELD_IDS)
    assert all(f.field != "hallucinated" for f in run.extraction.fields)


def test_extract_unusable_output_is_visible_error(monkeypatch, with_key):
    install(monkeypatch, FakeResponses(fake_response("I cannot produce JSON for this.", parsed=None)))
    with pytest.raises(ExtractionError) as info:
        extract_from_pdf(b"%PDF-1.4")
    assert info.value.code == "invalid_output" and info.value.retryable is True


def test_extract_refusal_is_reported(monkeypatch, with_key):
    files = install(monkeypatch, FakeResponses(fake_response(None, refusal=True)))
    with pytest.raises(ExtractionError) as info:
        extract_from_pdf(b"%PDF-1.4")
    assert info.value.code == "refusal"
    assert files.deleted == ["file_test123"]  # cleanup runs on every path


def test_extract_truncation_is_reported(monkeypatch, with_key):
    resp = fake_response("{", status="incomplete", parsed=None)
    resp.incomplete_details = SimpleNamespace(reason="max_output_tokens")
    install(monkeypatch, FakeResponses(resp))
    with pytest.raises(ExtractionError) as info:
        extract_from_pdf(b"%PDF-1.4")
    assert info.value.code == "truncated" and info.value.retryable is True


def _status_error(cls, status: int):
    request = httpx_mod.Request("POST", "https://api.openai.com/v1/responses")
    return cls("boom", response=httpx_mod.Response(status, request=request), body=None)


@pytest.mark.parametrize(
    "error, code, retryable",
    [
        (lambda: _status_error(openai.AuthenticationError, 401), "auth", False),
        (lambda: _status_error(openai.RateLimitError, 429), "rate_limit", True),
        (lambda: _status_error(openai.BadRequestError, 400), "bad_request", False),
        (lambda: _status_error(openai.InternalServerError, 503), "api", True),
        (lambda: openai.APIConnectionError(request=httpx_mod.Request("POST", "https://api.openai.com")), "network", True),
    ],
)
def test_extract_maps_api_errors(monkeypatch, with_key, error, code, retryable):
    files = install(monkeypatch, FakeResponses(error=error()))
    with pytest.raises(ExtractionError) as info:
        extract_from_pdf(b"%PDF-1.4")
    assert info.value.code == code
    assert info.value.retryable is retryable
    assert files.deleted == ["file_test123"]


def test_upload_failure_is_mapped_and_nothing_to_delete(monkeypatch, with_key):
    files = install(monkeypatch, FakeResponses(fake_response("{}")), FakeFiles(error=_status_error(openai.RateLimitError, 429)))
    with pytest.raises(ExtractionError) as info:
        extract_from_pdf(b"%PDF-1.4")
    assert info.value.code == "rate_limit"
    assert files.deleted == []
