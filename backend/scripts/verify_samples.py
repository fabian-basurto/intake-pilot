"""LIVE verification: runs the real extraction on each synthetic sample packet and
checks the review against the expected outcomes from the handoff.

Needs OPENAI_API_KEY (backend/.env is read). Costs real tokens.

Run from backend/:
    python scripts/verify_samples.py               # all three packets
    python scripts/verify_samples.py incomplete    # one packet

Full extraction + review JSON for each packet is written to backend/verify-output/
(git-ignored) so prompt issues can be inspected.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import MODEL_ID, SAMPLES_DIR, api_key_configured  # noqa: E402
from app.draft import build_draft  # noqa: E402
from app.extract import ExtractionError, extract_from_pdf  # noqa: E402
from app.rules import evaluate  # noqa: E402

EXPECTED: dict[str, dict] = {
    "packet_complete": {"attention": 0, "flagged": {}, "pages": 5},
    "packet_incomplete": {"attention": 2, "flagged": {"doc_recent_labs": "not_found", "insurance_evidence": "not_found"}, "pages": 3},
    "packet_ambiguous": {"attention": 1, "flagged": {"infusion_frequency": "needs_review"}, "pages": 5},
}


def main() -> int:
    if not api_key_configured():
        print("OPENAI_API_KEY is not set. Copy backend/.env.example to backend/.env and add a key.")
        return 2

    only = sys.argv[1].removeprefix("packet_").removesuffix(".pdf") if len(sys.argv) > 1 else None
    names = [n for n in EXPECTED if not only or n == f"packet_{only}"]
    if not names:
        print(f'Unknown packet "{only}". Use one of: complete, incomplete, ambiguous.')
        return 2

    out_dir = BACKEND_DIR / "verify-output"
    out_dir.mkdir(exist_ok=True)
    print(f"model: {MODEL_ID}\n")

    failures = 0
    for name in names:
        path = SAMPLES_DIR / f"{name}.pdf"
        if not path.is_file():
            print(f"{name}.pdf ... MISSING (run: python scripts/generate_samples.py)")
            failures += 1
            continue
        print(f"{name}.pdf ... ", end="", flush=True)
        try:
            run = extract_from_pdf(path.read_bytes(), path.name)
        except ExtractionError as err:
            failures += 1
            print(f"ERROR [{err.code}]: {err.message}")
            continue

        review = evaluate(run.extraction)
        draft = build_draft(review, run.extraction, f"{name}.pdf")
        (out_dir / f"{name}.json").write_text(
            json.dumps(
                {
                    "model": run.model,
                    "usage": run.usage,
                    "duration_ms": run.duration_ms,
                    "extraction": run.extraction.model_dump(),
                    "review": review.model_dump(by_alias=True),
                    "draft": draft,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        print(f"{run.duration_ms / 1000:.1f}s, {run.usage['input_tokens']} in / {run.usage['output_tokens']} out")
        print(f"  headline: {review.headline}")
        flagged = [i for i in review.items if i.status in ("not_found", "needs_review")]
        for f in flagged:
            print(f"  flagged:  {f.id} -> {f.status}  ({f.detail})")
        for u in review.items:
            if u.status == "info" and any(r.status == "uncertain" for r in u.field_records):
                print(f"  info/uncertain: {u.id}  ({u.detail})")

        exp = EXPECTED[name]
        problems: list[str] = []
        if review.attention_count != exp["attention"]:
            problems.append(f"expected {exp['attention']} attention item(s), got {review.attention_count}")
        for rid, status in exp["flagged"].items():
            item = next((i for i in review.items if i.id == rid), None)
            if item is None or item.status != status:
                problems.append(f"expected {rid} = {status}, got {item.status if item else 'missing'}")
        for f in flagged:
            if f.id not in exp["flagged"]:
                problems.append(f"unexpected flag {f.id} = {f.status}")

        def value(rid: str) -> str:
            item = next((i for i in review.items if i.id == rid), None)
            return (item.value if item else None) or ""

        if not re.search(r"testpatient", value("patient_name"), re.I):
            problems.append(f'patient_name unexpected: "{value("patient_name")}"')
        if "1979" not in value("patient_dob"):
            problems.append(f'patient_dob unexpected: "{value("patient_dob")}"')
        if "K51.90" not in value("icd10_code"):
            problems.append(f'icd10_code unexpected: "{value("icd10_code")}"')
        if not re.search(r"sampleton", value("provider_name"), re.I):
            problems.append(f'provider_name unexpected: "{value("provider_name")}"')
        if len(run.extraction.page_summary) != exp["pages"]:
            problems.append(f"page_summary has {len(run.extraction.page_summary)} pages, expected {exp['pages']}")

        if problems:
            failures += 1
            for p in problems:
                print(f"  MISMATCH: {p}")
        else:
            print("  matches expected outcome")
        if name == "packet_incomplete":
            print(f"\n--- draft ({name}) ---\n{draft}\n--- end draft ---")
        print()

    print(
        f"{failures} packet(s) did not match. See verify-output/*.json."
        if failures
        else "all packets match the expected outcomes"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())


