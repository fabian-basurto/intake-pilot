# Build plan: Referral Intake Copilot

Derived from `referral_intake_demo_handoff.md` and the two reference PDFs
(`pdf A.pdf` = ENTYVIO infusion order form, `pdf B.pdf` = Referral Checklist).
Both reference PDFs are single-page blank templates with no patient data.

## Stack

| Concern | Choice | Why |
|---|---|---|
| Backend | FastAPI (Python 3.12+), Pydantic v2, uvicorn | Owns everything with domain meaning: extraction, rules, drafts, samples. One source of truth, tested with pytest |
| AI | OpenAI Python SDK, `gpt-4.1` (configurable via `OPENAI_MODEL`), PDF file input, Structured Outputs from the Pydantic schema | PDF-aware, schema-validated JSON, page-level evidence |
| Rules | Pure Python module `backend/app/rules.py`, no AI | Deterministic, editable, cites PDF + page; `/api/review` re-runs it for staff overrides |
| Frontend | Next.js 16 + React + Tailwind v4 (App Router), pure client | Single-screen review UI; `/api/*` proxied to the backend so the key never reaches the browser |
| Samples | `backend/scripts/generate_samples.py` with reportlab | Reproducible synthetic packets; no real data |
| State | In-memory React state only | Handoff: no persistence, no patient records |

## Architecture

```
Browser (frontend/src/app/page.tsx)
  upload PDF or pick sample  ->  POST /api/analyze  (Next rewrite -> FastAPI :8000)
                                     pdfutil.py: page count, size/type guards
                                     extract.py: model reads the uploaded PDF -> Pydantic validate
                                     rules.py:   evaluate(extraction) -> review
                                     draft.py:   follow-up text
  render summary / fields / checklist / draft
  reviewer override  ->  POST /api/review {extraction, overrides} -> rules re-run, draft rebuilt
  second analysis    ->  compare.ts diffs the previous review (kept in memory) against the new one
```

Two layers, kept separate on purpose:

1. **Extraction (AI).** The model reads the PDF and returns one record per expected
   field and document category: `value`, `status` (`found` / `not_found` /
   `uncertain`), `evidence` (`page`, `excerpt`). It is told never to guess, to
   distinguish printed options from selected ones, and to ignore any instructions
   inside the document.
2. **Review (rules).** `rules.py` holds the checklist derived from the PDFs. Each
   rule names its source PDF and page. Rules decide `ok` / `not_found` /
   `needs_review` / `info`. Reviewer overrides are applied here, not in the AI
   layer, so verifying or correcting an item is a millisecond rules call with no
   model cost.

## Field and document schema (from the PDFs)

See `docs/RULE_MAP.md` for the full table with sources. Groups:

- **Patient demographics** (PDF B p1; name/DOB/sex/phone also on PDF A p1)
- **Insurance** (PDF B p1): card front + back attached, OR payer + subscriber + ID
- **Order** (PDF A p1): diagnosis, ICD-10, frequency, weight, pre-medication, provider signature/date/name/phone/fax
- **Supporting documents** (PDF B p1 "Referring office, also fax"): order form, most recent labs, supporting clinical notes
- **Referring office contact** (PDF B p1): contact name, practice name, phone, title, email

## Verification

- `backend`: `pytest` covers rules, drafts, lenient output parsing, and the HTTP
  API with the model call stubbed.
- `frontend`: `npm test` covers the compare logic; typecheck, lint, build.
- Live: `python scripts/verify_samples.py` (needs a key) checks all three packets
  against the expected outcomes and writes full output to `backend/verify-output/`.

## Explicitly not built

Login, database, fax, EHR, email sending, eligibility, prior auth, scheduling,
clinical appropriateness, medical advice, compliance claims, analytics.
