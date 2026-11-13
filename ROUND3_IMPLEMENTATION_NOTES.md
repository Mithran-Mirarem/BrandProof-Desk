# BrandProof Desk Round 3 — implementation notes

Base source snapshot: `42d2172b7dad2591240d1c49722da7e971aac32a` (Round 2 source ZIP).

## Implemented

1. **Visual brand compliance**: approved HEX palette settings, approved logo-reference upload/removal, image upload and screening, dominant-colour extraction, RGB tolerance comparison, perceptual-hash logo candidate score, optional Tesseract OCR restricted-term checks, saved visual history and SHA-256/image dimensions.
2. **Evidence provenance and expiry**: SQLite evidence registry with source, URL, owner, version, valid-from/until and state plus a retained creation/update/deletion event history; migration of the existing JSON evidence set; expiry/scheduled/soon-expiry computation; expired/future evidence excluded from LLM context and relevant lifecycle findings added to reviews; provenance metadata included in PDF reports.
3. **Governance analytics**: text + visual finding categories/severities, review channels/statuses, approval rate, recurring issue labels and 14-day combined activity.

The original review, decision, history, file intake and PDF reporting workflows remain in the source.

## Validation completed in this environment

- `pytest -q`: **12 passed**.
- `python -m compileall -q backend/app`: passed.
- TypeScript transpiler JSX syntax check: `frontend/src/main.jsx` and `frontend/src/Round3.jsx` passed.
- FastAPI TestClient checks cover evidence CRUD and audit events, palette configuration, logo-reference management, creative upload, persisted visual metadata and analytics aggregation.
- PDF report builder smoke test passed.

## Validation not completed

`npm ci` could not finish because this environment could not resolve `registry.npmjs.org` (`EAI_AGAIN`). Therefore a Vite production bundle was **not** generated or visually browser-tested here. Run the frontend build locally before pushing/deploying:

```powershell
cd frontend
npm ci
npm run build
```

## Windows update steps

1. In your existing Git clone, create a backup branch before applying the patch:

```powershell
git switch -c round3/brandproof-desk
```

2. Extract `BrandProof-Desk-Round3-Patch.zip` into the root of that existing Git clone, allowing it to overwrite the listed files. This patch does not include or replace `.git`.
3. Update backend dependencies and run tests:

```powershell
cd backend
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
$env:PYTHONPATH = "."
pytest -q ..\tests
```

4. Build frontend:

```powershell
cd ..\frontend
npm ci
npm run build
```

5. Start backend and frontend and test the three Round 3 pages. Confirm logo upload, palette save, visual image review, evidence expiry and PDF provenance, and analytics refresh.
6. Commit and push only after local testing:

```powershell
git status --short
git add README.md ROUND3_IMPLEMENTATION_NOTES.md docs backend frontend tests
git commit -m "Build Round 3 visual compliance, evidence lifecycle and analytics"
git push -u origin round3/brandproof-desk
```

Merge to `main`/deploy only after checking the Vite build and live backend configuration.

## Important limits

- The API is still a single-workspace demo without authentication or tenant isolation. Use synthetic data only.
- Visual logo match is a perceptual-hash candidate signal, not proof of identity; RGB colour distance is approximate.
- OCR needs Tesseract installed separately and available on `PATH`; otherwise the API reports OCR unavailable.
- The local backend, SQLite and Ollama remain dependent on the host machine and network when exposed through a Quick Tunnel.
