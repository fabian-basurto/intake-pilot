# Referral Intake Copilot (demo)

AI-assisted referral packet review on **synthetic data only**. A FastAPI backend
reads one PDF packet with an OpenAI model, applies deterministic checklist rules derived
from two reference forms, and produces an editable follow-up draft. A Next.js
frontend lets staff upload, review evidence, verify or correct findings, and
compare packets. Nothing is stored or sent.

Built from `referral_intake_demo_handoff.md`. Plan: `docs/PLAN.md`.
Rule provenance: `docs/RULE_MAP.md`.

```
referral-intake-copilot/
  backend/    FastAPI (Python 3.12+): extraction, rules, drafts, samples, tests
  frontend/   Next.js 16 + React + Tailwind: the single-screen review UI
  docs/       plan and rule map
```

## Run it

Two terminals. Requires Python 3.12+, Node 20+, and an OpenAI API key.

**Backend** (port 8000):

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env              # put your OPENAI_API_KEY in .env
python scripts\generate_samples.py  # writes samples\packet_*.pdf (synthetic)
uvicorn app.main:app --reload --port 8000
```

**Frontend** (port 3000):

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. The frontend proxies `/api/*` to the backend
(`BACKEND_URL` in `frontend/.env.local` if it is not on `127.0.0.1:8000`), so the
browser never needs CORS and the API key never leaves the backend.
Interactive API docs: http://localhost:8000/api/docs.

## Checks

Backend (offline, no key, no cost):

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest     # rules, drafts, output parsing, HTTP API (model stubbed)
```

Frontend:

```powershell
cd frontend
npm test            # compare logic
npm run typecheck
npm run lint
npm run build
```

Live (needs the key, costs tokens): runs the real extraction on each sample
packet and compares the review against the expected outcomes. Full output per
packet lands in `backend/verify-output/` (git-ignored).

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\verify_samples.py              # all three packets
.\.venv\Scripts\python.exe scripts\verify_samples.py incomplete   # one packet
```

Expected outcomes:

| Packet | Headline | Flagged |
|---|---|---|
| `packet_complete.pdf` | No documentation gaps detected | none |
| `packet_incomplete.pdf` | Review required — 2 items | Most recent labs, Insurance evidence (not found) |
| `packet_ambiguous.pdf` | Review required — 1 item | Infusion frequency (needs staff review) |

Only claim these in a demo after `verify_samples.py` passes on your key.

## Demo walkthrough (3–5 minutes)

1. Click **Missing documentation**, then **Analyze packet**. Watch the upload
   bar, then the model reading the packet (typically 20–60 s).
2. Summary reads **Review required — 2 items**: *Most recent labs* and *Insurance
   evidence* are **Not found in uploaded packet**. Everything else is **Found**
   with a page reference. The **Action needed** list links to each row.
3. Click **Insurance evidence** to see why, the extraction evidence, and the
   checklist source (Reference B, page 1). Click **Mark as verified**, add a note
   such as "Card on file from prior visit", save. The backend re-runs the rules,
   the summary drops to 1 item, and the draft no longer asks for the card.
4. Edit the draft, click **Copy**. There is no send button.
5. Click **Complete packet**, analyze again: **No documentation gaps detected**,
   still pending staff verification; the draft becomes an acknowledgement. The
   **Compare** panel shows labs and insurance moving from Not found to Found.
6. Optional: **Ambiguous packet** marks both frequency options on the order form;
   the result is **Needs staff review** on *Infusion frequency*, with the model's
   note, not a guessed answer. **Correct value** resolves it.

Uploading your own PDF works the same way. Anything the rules cannot find is
reported as *Not found in uploaded packet*, never as a claim about the
referring office.

## How it works

```
Browser (Next.js, React)              FastAPI backend (Python)
  pick sample / upload PDF  ------>   POST /api/analyze   multipart: file | sample
                                        pdfutil.py   page count, size and type guards
                                        extract.py   model reads the PDF, returns
                                                     Pydantic-validated JSON (structured output)
                                        rules.py     deterministic checklist, cites PDF + page
                                        draft.py     follow-up text
  summary / fields / checklist <-----  JSON (camelCase envelope)
  staff verify or correct   ------>   POST /api/review    rules re-run, no model call
  compare two runs                    (client side, src/lib/compare.ts)
```

API: `GET /api/health`, `GET /api/samples`, `GET /api/samples/{key}/file`,
`GET /api/rules`, `POST /api/analyze`, `POST /api/review`.

Backend modules:

- `app/schema.py` — field and document ids, Pydantic extraction contract.
- `app/prompt.py` — field guide given to the model (from the reference forms).
- `app/rules.py` — rules with `source` (PDF + page) on every entry. Edit here.
- `app/draft.py` — follow-up draft builder.
- `app/extract.py` — model call, error mapping, lenient repair of model output.
- `scripts/generate_samples.py` — synthetic packets (reportlab).

## Status language

- **Found** — value observed; evidence page shown.
- **Not found in uploaded packet** — not detected in this upload. Not a claim
  that the referring office failed to send it.
- **Needs staff review** — conflicting, illegible, or partially completed.
- **Verified by staff / Corrected by staff** — reviewer override, in memory only.

## Safety and scope

The API key is read only by the backend from `backend/.env`. PDF contents are
never logged. Model output is treated as untrusted data and validated. No
login, database, fax, EHR/EMR, email sending, eligibility, prior authorization,
scheduling, medication appropriateness, medical advice, or compliance claims.
