"""HTTP-level checks with FastAPI's TestClient. The model call is stubbed; no API key needed."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.extract import ExtractionRun
from app.main import app
from scripts.generate_samples import build_packet

client = TestClient(app)


@pytest.fixture(scope="module")
def incomplete_pdf() -> bytes:
    return build_packet("incomplete")


def test_health_reports_key_state(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY_UNUSED", raising=False)
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["apiKeyConfigured"] is False
    assert [s["key"] for s in body["samples"]] == ["complete", "incomplete", "ambiguous"]


def test_rules_endpoint_lists_sources():
    r = client.get("/api/rules")
    assert r.status_code == 200
    assert any(row["id"] == "insurance_evidence" for row in r.json())


def test_analyze_without_file_is_400():
    r = client.post("/api/analyze", data={"nothing": "1"})
    assert r.status_code == 400
    assert r.json() == {"error": "No PDF file was provided.", "code": "bad_request", "retryable": False}


def test_analyze_rejects_text_file():
    r = client.post("/api/analyze", files={"file": ("notes.txt", b"plain text", "text/plain")})
    assert r.status_code == 400
    assert r.json()["error"] == "Only PDF files are supported."


def test_analyze_rejects_renamed_text():
    r = client.post("/api/analyze", files={"file": ("fake.pdf", b"this is not really a pdf", "application/pdf")})
    assert r.status_code == 400
    assert r.json()["error"] == "The file does not look like a PDF."


def test_analyze_rejects_empty_file():
    r = client.post("/api/analyze", files={"file": ("empty.pdf", b"", "application/pdf")})
    assert r.status_code == 400
    assert r.json()["error"] == "The uploaded file is empty."


def test_analyze_unknown_sample():
    r = client.post("/api/analyze", data={"sample": "nope"})
    assert r.status_code == 400
    assert 'Unknown sample "nope"' in r.json()["error"]


def test_analyze_without_key_is_visible_error(monkeypatch, incomplete_pdf):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY_UNUSED", raising=False)
    r = client.post("/api/analyze", files={"file": ("packet.pdf", incomplete_pdf, "application/pdf")})
    assert r.status_code == 500
    body = r.json()
    assert body["code"] == "missing_api_key"
    assert "OPENAI_API_KEY" in body["error"]


def test_analyze_end_to_end_with_stubbed_model(monkeypatch, incomplete_pdf, incomplete_extraction):
    seen: dict[str, int] = {}

    def fake_extract(data: bytes, *_) -> ExtractionRun:
        seen["bytes"] = len(data)
        return ExtractionRun(extraction=incomplete_extraction, model="stub-model", usage={"input_tokens": 10, "output_tokens": 5}, duration_ms=7)

    monkeypatch.setattr("app.main.extract_from_pdf", fake_extract)
    r = client.post("/api/analyze", files={"file": ("my packet.pdf", incomplete_pdf, "application/pdf")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert seen["bytes"] == len(incomplete_pdf)
    assert body["file"] == {"name": "my packet.pdf", "sizeBytes": len(incomplete_pdf), "pages": 3, "synthetic": False, "url": None}
    assert body["model"] == {"id": "stub-model", "usage": {"input_tokens": 10, "output_tokens": 5}, "durationMs": 7}
    assert body["review"]["attentionCount"] == 2
    assert body["review"]["headline"].startswith("Review required")
    flagged = sorted(i["id"] for i in body["review"]["items"] if i["status"] == "not_found")
    assert flagged == ["doc_recent_labs", "insurance_evidence"]
    assert "fieldRecords" in body["review"]["items"][0]
    assert "page_summary" in body["extraction"]
    assert "most recent labs" in body["draft"]


def test_review_endpoint_applies_overrides(incomplete_extraction):
    payload = {
        "file_name": "packet_incomplete.pdf",
        "extraction": incomplete_extraction.model_dump(),
        "overrides": {"insurance_evidence": {"kind": "verified", "note": "Card on file"}},
    }
    r = client.post("/api/review", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["review"]["attentionCount"] == 1
    item = next(i for i in body["review"]["items"] if i["id"] == "insurance_evidence")
    assert item["status"] == "ok"
    assert item["detail"] == "Verified by staff: Card on file"
    assert item["override"] == {"kind": "verified", "value": None, "note": "Card on file"}
    assert "insurance card" not in body["draft"].lower()
    assert "most recent labs" in body["draft"]


def test_review_round_trips_analyze_output(monkeypatch, incomplete_pdf, incomplete_extraction):
    """The extraction returned by /api/analyze can be posted back to /api/review unchanged."""
    monkeypatch.setattr(
        "app.main.extract_from_pdf",
        lambda data, *_: ExtractionRun(extraction=incomplete_extraction, model="stub", usage={"input_tokens": 1, "output_tokens": 1}, duration_ms=1),
    )
    analyzed = client.post("/api/analyze", files={"file": ("p.pdf", incomplete_pdf, "application/pdf")}).json()
    r = client.post("/api/review", json={"file_name": analyzed["file"]["name"], "extraction": analyzed["extraction"], "overrides": {}})
    assert r.status_code == 200, r.text
    assert r.json()["review"] == analyzed["review"]
    assert r.json()["draft"] == analyzed["draft"]


def test_review_rejects_bad_body():
    r = client.post("/api/review", json={"extraction": {"fields": "nope"}})
    assert r.status_code == 400
    body = r.json()
    assert body["code"] == "bad_request"
    assert body["error"].startswith("Invalid request")


def test_sample_file_is_served(monkeypatch, tmp_path):
    (tmp_path / "packet_complete.pdf").write_bytes(build_packet("complete"))
    monkeypatch.setattr("app.samples.SAMPLES_DIR", tmp_path)
    r = client.get("/api/samples/complete/file")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"
    missing = client.get("/api/samples/incomplete/file")
    assert missing.status_code == 404
    assert client.get("/api/samples/nope/file").status_code == 404


def test_sample_analysis_uses_registry(monkeypatch, tmp_path, incomplete_extraction):
    (tmp_path / "packet_incomplete.pdf").write_bytes(build_packet("incomplete"))
    monkeypatch.setattr("app.samples.SAMPLES_DIR", tmp_path)
    monkeypatch.setattr(
        "app.main.extract_from_pdf",
        lambda data, *_: ExtractionRun(extraction=incomplete_extraction, model="stub", usage={"input_tokens": 1, "output_tokens": 1}, duration_ms=1),
    )
    r = client.post("/api/analyze", data={"sample": "incomplete"})
    assert r.status_code == 200, r.text
    assert r.json()["file"]["synthetic"] is True
    assert r.json()["file"]["url"] == "/api/samples/incomplete/file"
    assert r.json()["file"]["pages"] == 3


