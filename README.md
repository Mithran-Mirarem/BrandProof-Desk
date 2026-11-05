# BrandProof Desk

**CodeNexus India 2026 — Round 2 functional MVP**
Evidence-linked, human-controlled brand governance review for text, PDF and DOCX content.

## What works in this build

- Brand evidence vault: edit brand name, tone guidance, required/restricted terminology and approved fact records.
- Content intake: paste content or upload PDF, DOCX or TXT (8 MB max).
- Context-dependent review plan: selects exact-term, claim and tone checks based on the draft.
- Deterministic checks: restricted phrases, brand naming and high-risk/quantified claims.
- Evidence retrieval: keyword-based retrieval over approved fact records; results retain source IDs, names and validity dates.
- Optional live LLM analysis through Adaption Responses API (Qwen 3.5 397B by default), with structured findings and suggested revisions.
- Transparent fallback: without an API key, exact-rule and claim checks remain usable and the UI clearly labels the run as rule-engine fallback. It does not pretend that a live LLM ran.
- Review outcomes: approve, request changes or escalate; apply a suggested revision; maintain an audit history.
- Export a review report as Markdown.

## Stack

- Frontend: React 19 + Vite + custom CSS
- API: Python 3.11 + FastAPI
- Storage: SQLite by default for a self-contained demo (the Round 1 proposal planned MongoDB Atlas; this is a disclosed Round 2 implementation simplification for reliable local judging. A MongoDB adapter can replace this storage layer in a later iteration.)
- AI: Adaption Responses API; `qwen3.5-397b` is the default model candidate and can be changed via environment variable.
- Document extraction: PyMuPDF and python-docx

## Run locally on Windows

Prerequisites: Python 3.11+ and Node.js 20+.

### 1. Backend

```powershell
cd backend
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Open .env and add ADAPTION_API_KEY if you have it
python run.py
```

API health: http://localhost:8000/api/health
Interactive API docs: http://localhost:8000/docs

### 2. Frontend (new terminal)

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL printed in the terminal (normally http://localhost:5173).

If the API is hosted at a different URL, create `frontend/.env` with:

```env
VITE_API_URL=https://your-api-host
```

Then rebuild with `npm run build`.

## Enable live Adaption AI

1. Create/use your Adaption account and generate an API key.
2. Put the key only in `backend/.env`:

```env
ADAPTION_API_KEY=
ADAPTION_BASE_URL=https://api.prod.adaptionlabs.ai/api/v1
ADAPTION_MODEL=qwen3.5-397b
```

3. Restart the backend and check `/api/status`. It should return `ai_configured: true`.

The backend sends draft content and relevant approved fact excerpts to the external model for semantic analysis. Do not upload sensitive or confidential brand material unless you have permission and have reviewed the provider's data handling terms. The key is never sent to the browser.

Adaption API docs: https://docs.adaptionlabs.ai/api/resources/responses/methods/create

## Judge demo — 3 minutes

1. Open **Brand evidence vault** and show the preloaded Northstar Analytics demo brand.
2. Open **New review** and click **Load sample draft**.
3. Run the review. Demonstrate the restricted-phrase and unsupported-claim findings, with the approved facts shown beside them.
4. Open a finding and explain that missing evidence is marked “needs review”, not “false”.
5. Apply the suggested revision, then choose **Request changes** or **Approve** to show human control.
6. Open **Review history** and the review's audit history.
7. Show `/api/status` to prove whether live Adaption AI is configured; do not claim live AI if it is in fallback mode.

## Important limitations (be transparent)

- Brand evidence retrieval is keyword-based in this MVP, not vector/embedding retrieval.
- The LLM call is semantic assistance, not legal advice or an independent truth oracle.
- The deterministic claim detector flags numeric/absolute language for evidence review; it cannot prove truth or falsity.
- Visual logo/colour analysis and accessibility checks are Round 3 improvements, not implemented in this Round 2 MVP.
- This MVP has a demo workspace and no production-grade multi-tenant authentication. Do not use it with real confidential client documents.
- Human approval is a recorded workflow decision; the app does not publish to external channels.

## Repository structure

```text
brandproof-desk/
  backend/
    app/{main.py,db.py,ai.py,review.py}
    requirements.txt
    .env.example
    Dockerfile
    run.py
  frontend/
    src/{main.jsx,style.css}
    index.html
    package.json
  docs/
  tests/
```

## Round 2 / Round 3 boundary

Round 2: one complete text/PDF/DOCX review workflow with evidence retrieval, deterministic and optional LLM checks, suggestions and approval history.
Round 3 planned improvements: (1) supported visual brand checks for logo/colour usage; (2) claim provenance and expiry management; (3) governance insights showing recurring issues and unclear guidelines.

## Disclosure

This is a solo implementation by VP Mithramoorthy. The system uses third-party libraries and, when configured, the Adaption AI Responses API with the selected model. The AI-generated evaluation is labelled as such; rules and approval actions are deterministic application code. No existing completed application is being represented as new hackathon work. Update this disclosure and your repository history to reflect the actual work and any assistance/tools used.
