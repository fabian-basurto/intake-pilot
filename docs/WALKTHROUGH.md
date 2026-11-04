# Referral Intake Copilot: walkthrough

Live pilot: https://intake-pilot-eight.vercel.app/

Synthetic data only. This is a demonstration of a first-pass administrative
intake assistant. It is not a clinical, coverage, or eligibility decision tool,
and it sends nothing to anyone.

## 1. What it is

A referral packet is the bundle of documents a clinic sends to an infusion
center to start a treatment order: an order form, insurance information,
patient demographics, labs, and clinical notes. Staff must check that the
packet is complete before intake can proceed.

The pilot does that check in three steps:

1. An AI model reads the uploaded PDF and extracts the administrative facts
   (name, date of birth, insurer, diagnosis code, provider, and so on), each
   with the page it came from.
2. Fixed, written rules decide what needs attention. The rules come from the
   two reference forms supplied with the handoff. The AI never decides what is
   missing.
3. Staff review the findings, verify or correct them, and copy a follow-up
   request to the referring office. Nothing is sent automatically.

## 2. How it works

```
Browser (Next.js on Vercel)
  upload PDF or pick a sample  --POST /api/analyze-->  proxied to FastAPI backend
                                                         1. check the file is a real PDF
                                                         2. send the PDF to an OpenAI model
                                                            and receive structured JSON
                                                         3. run the fixed checklist rules
                                                         4. build the follow-up draft
  summary, checklist, evidence, draft  <--------------  JSON
  verify / correct a finding  --POST /api/review-->  rules re-run, draft rebuilt (no AI call)
```

The frontend and backend are separate projects in one repository:

- `frontend/`: Next.js and React. It holds the screen and forwards `/api/*` to
  the backend. It never sees the API key.
- `backend/`: FastAPI on Python. It holds the AI call, the rules, the draft,
  and the sample packets.
- `docs/RULE_MAP.md`: every rule and the reference page it comes from.

## 3. What is implemented

| Area | What it does |
|---|---|
| Intake | Upload one PDF (up to 20 MB, up to 100 pages), or pick one of three synthetic sample packets. Non-PDF, empty, and fake-PDF files are rejected with a clear message. |
| Progress | Attach, Analyze, Review steps; upload percentage; elapsed time while the model reads the packet; a status badge. |
| Extraction | An OpenAI model reads the PDF and returns structured fields. Each field has a value, a status (found, not found, or uncertain), and evidence (page and excerpt). The model is told never to guess. |
| Output checking | The response is validated against a schema. Unknown fields are dropped and unknown statuses become "uncertain", so a malformed answer cannot silently pass. |
| Rules | 30 checklist rules, each citing the reference form and section it comes from. Required items that are missing are flagged. Optional items are shown but never counted. |
| Insurance rule | Satisfied by either both card images, or payer plus subscriber plus member ID. |
| Staff review | Mark an item verified, or correct its value, with an optional note. The summary and draft update at once. Undo is available. |
| Follow-up draft | An editable message asking only for what is missing or unclear. Copy button. No send button. |
| Compare | After a second analysis, shows which gaps resolved, which are new, and which changed, against any of the last six runs. |
| Export | Downloads the review as JSON. |
| Errors | Every failure shows a red box that says no results were produced. Quota, rate limit, bad key, refusal, and unreadable output each have their own message. |
| Privacy | The key stays on the server. The uploaded PDF is deleted from OpenAI storage after each analysis. Nothing is saved between sessions. |

## 4. What the results mean

Each status means one specific thing:

- **Found**: the value was read from the packet. The evidence page is shown.
- **Not found in uploaded packet**: nothing matching was detected in this upload.
  This does not mean the referring office failed to send it.
- **Needs staff review**: the value conflicts, is illegible, or is partly
  completed. The model does not guess.
- **Verified by staff / Corrected by staff**: a human decision, kept in memory
  for this session only.

The three samples are designed to show three different outcomes:

| Sample | Expected headline | Expected flags |
|---|---|---|
| Complete packet | No documentation gaps detected | None |
| Missing documentation | Review required, 2 items | Most recent labs; insurance evidence (not found) |
| Ambiguous packet | Review required, 1 item | Infusion frequency (needs staff review; both options are marked on the form) |

These are the expected results, taken from the synthetic packets' known
contents. Confirm them on the live site before presenting; see section 5.

## 5. How to test

### A. Walk through the live site (about 5 minutes)

1. Open https://intake-pilot-eight.vercel.app/. The header shows the
   "DEMO · SYNTHETIC DATA" badge.
2. Click **Missing documentation**, then **Analyze packet**. Watch the upload
   bar, then the reading step. Expect 20 to 60 seconds.
3. Check the headline: **Review required, 2 items**. Check that the Action
   needed list names labs and insurance evidence.
4. Click **Insurance evidence**. Read the reason, the extraction evidence, and
   the checklist source (Reference B, page 1). Click **Mark as verified**, add
   a note, and save. The headline drops to 1 item and the draft stops asking
   for the insurance card.
5. Edit the draft, then click **Copy** and paste it somewhere to confirm.
6. Click **Complete packet** and analyze again. Expect **No documentation gaps
   detected**. The Compare panel should show labs and insurance moving from
   not found to found.
7. Click **Ambiguous packet**. Expect a flag on infusion frequency, with the
   model's note explaining that both options are marked. Use **Correct value**
   to resolve it.
8. Optional: upload your own PDF. Anything missing is reported as not found.
   Upload a text file renamed to `.pdf` to see the rejection message.

### B. Check the backend directly

- Health: https://intake-pilot-eight.vercel.app/api/health should return
  `"ok": true`, `"apiKeyConfigured": true`, and the model name.
- Rules: https://intake-pilot-eight.vercel.app/api/rules lists all 30 rules
  with their sources.
- API docs: the backend's interactive documentation is at `/api/docs` on the
  backend host (not proxied to the frontend).

### C. Run the automated checks (no key needed)

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest     # 40 tests; the model call is stubbed
cd ..\frontend
npm test
npm run typecheck
npm run build
```

### D. Live accuracy check (needs an OpenAI key, costs a few cents)

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\verify_samples.py
```

This runs all three samples through the real model and compares the results
with section 4. Full output is saved to `backend/verify-output/`.

## 6. Known limits

- **The model call is the only live AI step.** Everything else is deterministic
  and tested. Extraction quality on unusual layouts is not guaranteed. A real
  packet may produce "needs staff review" more often than the samples do.
- **Synthetic data only.** The handoff forbids real patient data. Do not
  upload real packets to the public pilot.
- **No login.** Anyone with the link can use the pilot and spend the OpenAI
  credit behind it. Protect the deployment before sharing it widely.
- **In memory only.** Reviews, overrides, and compare history disappear on
  refresh or restart. Nothing is stored in a database.
- **Proxy timeouts.** A very slow analysis, or a large upload, can fail at the
  hosting layer. Samples are small and should not hit this.
- **No clinical judgment.** The tool flags missing paperwork. It does not
  check medication, dosing, or coverage.

## 7. Things to say when presenting

"This is a first-pass intake assistant. It reads a referral packet, pulls out
the key details, checks the documentation against a defined checklist, and
shows staff exactly where to follow up. Nothing is approved or sent
automatically."

Show one flagged item, its evidence, and the rule it comes from. The rule
citation is the part that makes the result checkable.
