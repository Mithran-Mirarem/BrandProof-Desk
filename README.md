# BrandProof Desk — Round 3

**Evidence-linked, human-controlled brand governance**

BrandProof Desk reviews marketing/product content against approved brand rules and source records. Round 3 adds three connected capabilities: visual creative screening, evidence provenance and expiry management, and governance analytics.

## Round 3 capabilities

### 1. Visual brand compliance

- Upload PNG, JPEG or WebP creative assets (8 MB maximum; 24 megapixels maximum).
- Configure up to 12 approved brand HEX colours; detected dominant colours are compared to the palette using an RGB-distance tolerance.
- Upload one approved logo reference; the visual service searches for a possible match using a perceptual-hash similarity score.
- If the Tesseract OCR engine is installed on the backend machine, extract image text and flag configured restricted terms.
- Save each visual screening with a SHA-256 checksum, findings and dominant-colour record.

**Interpretation boundary:** Logo similarity is a screening candidate, not proof of authenticity. RGB distance is not a certified colour-management workflow. OCR can misread small or stylised text. Results are advisory and require human verification.

### 2. Evidence provenance and expiry

- Maintain independent evidence records with claim, source name, source URL, owner, version, valid-from date, valid-until date and lifecycle state.
- Preserve an evidence audit trail for record creation, changed fields/version, and deletion; the registry UI can inspect each record history.
- Effective states include approved, expired, scheduled, pending verification and archived.
- Review retrieval only supplies currently approved records inside their validity window to the AI analysis.
- Relevant expired, future-dated or soon-to-expire records are surfaced as evidence-lifecycle findings instead of being silently treated as approved evidence.
- Existing Round 2 JSON facts are migrated into the evidence registry at database initialisation, preserving their IDs and source labels.

### 3. Governance analytics

- Aggregate text-review and visual-screening findings by category and severity.
- Show review channel, human decision status, approval rate, repeated issues and 14-day review/visual activity.
- Analytics are based on records stored in the current SQLite workspace.

## Existing Round 2 workflow retained

- React/Vite workspace, review form, TXT/PDF/DOCX extraction, brand rules and evidence vault.
- Python FastAPI service with deterministic phrase/claim checks and local Ollama/Qwen 3.5 4B analysis.
- Human approval, request-changes and escalation decisions, review history and audit events.
- PDF review reports, now including evidence owner, version, source URL and validity metadata.

## Technology stack

- Frontend: React 19, Vite 6.3.5, custom CSS, lucide-react.
- Backend: Python 3.11+, FastAPI, Uvicorn, Pydantic.
- AI: Ollama with `qwen3.5:4b` for contextual text analysis; visual checks are deterministic Python/Pillow algorithms.
- Storage: SQLite, with lightweight schema migrations.
- Documents: PyMuPDF, python-docx, ReportLab.
- Visual: Pillow, optional `pytesseract` Python wrapper and locally installed Tesseract OCR executable.
- Tests: pytest, FastAPI TestClient/HTTPX.

## Run locally on Windows

### Backend

```powershell
cd backend
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python run.py
```

The API is available at `http://localhost:8000`; OpenAPI docs are at `/docs`.

Set `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_NUM_CTX` and `BRANDPROOF_DB_PATH` in `backend/.env` as needed. Keep Ollama running separately. The default model is `qwen3.5:4b`.

### Frontend

```powershell
cd frontend
npm ci
npm run dev
```

For a separate API host, set `VITE_API_URL` in `frontend/.env` before building.

### Optional OCR setup on Windows

The Python dependency `pytesseract` is only a wrapper. Install the Tesseract OCR executable separately and ensure `tesseract.exe` is on `PATH`. Without it, visual palette and logo screening still work, but text-in-image checks explicitly report OCR as unavailable.

## API additions

| Endpoint | Purpose |
|---|---|
| `GET /api/evidence` | List provenance-aware evidence records |
| `POST /api/evidence` | Create an evidence record |
| `PUT /api/evidence/{id}` | Update its source, owner, version, validity and state |
| `DELETE /api/evidence/{id}` | Delete a record while retaining its audit events |
| `GET /api/evidence/{id}/history` | Read evidence lifecycle/audit events |
| `GET /api/visual/config` | Read palette and logo-reference configuration |
| `PUT /api/visual/config` | Save approved HEX palette |
| `POST /api/visual/logo-reference` | Upload approved reference logo |
| `DELETE /api/visual/logo-reference` | Remove logo reference |
| `POST /api/visual/reviews` | Analyse a creative image |
| `GET /api/visual/reviews` | List saved visual screening history |
| `GET /api/analytics` | Return governance aggregates and timeline |

## Judge walkthrough

1. Open **Visual compliance**. Set the approved palette and upload the official logo reference.
2. Upload a creative asset and inspect the dominant colours, logo candidate score, OCR availability and findings.
3. Open **Evidence registry**. Inspect provenance fields, edit an evidence version and try a deliberately expired test record. Confirm that expired records are not sent as approved evidence in a text review.
4. Open **New review** and load the sample draft. Review the evidence-expiry warning and existing restricted-phrase/claim checks.
5. Record a human decision, export a PDF and confirm that evidence owner/version/validity data appear in the report.
6. Open **Governance analytics** and inspect category/severity aggregates, decisions, recurring issues and the activity timeline.

## Important limitations and safe use

- This is a single-workspace demonstration, not a production multi-tenant service. Authentication, role-based access and tenant isolation are not implemented.
- The public demo API is unauthenticated and must use synthetic/non-confidential data only. Do not expose secrets or real customer documents.
- Evidence retrieval remains keyword-based; vector/embedding retrieval is not implemented.
- Local backend, SQLite and Ollama require the participant's machine and network to remain available when using a temporary Cloudflare Quick Tunnel.
- No visual algorithm guarantees exact logo authenticity or colour correctness. All findings are advisory and require a human decision.
- The approval workflow records decisions; it does not publish content to an external channel.

## Repository structure

```text
backend/app/{main.py,db.py,ai.py,review.py,report.py,visual.py}
frontend/src/{main.jsx,Round3.jsx,style.css,round3.css}
tests/{test_review.py,test_round3.py}
docs/ROUND3_SCOPE.md
```

## Development disclosure

This is a solo participant project by VP Mithramoorthy. ChatGPT/AI assistance was used for coding support, code review, debugging and test drafting. The participant remains responsible for configuration, integration, validation and final decisions. Visual screening is implemented with deterministic image-processing heuristics; it is not represented as an independent vision model or a definitive legal/brand certification.
