# BrandProof Desk — Round 2 submission draft

**Team:** MIRAMITHRAN30
**Participant:** VP Mithramoorthy (solo participant)
**Round:** 2 — Functional Product Development

## Working product
BrandProof Desk is a text-first brand-governance MVP. A reviewer can configure approved brand tone guidance, required/restricted terminology and approved fact records; submit pasted text or a PDF/DOCX/TXT draft; run selected checks; inspect issue explanations and source IDs; apply available revisions; and record an approval, changes-requested or escalation decision with an audit event.

## Current implementation status
- [x] Brand evidence vault with configurable rules and approved fact records
- [x] Pasted-text content intake
- [x] PDF, DOCX and TXT text extraction
- [x] Deterministic terminology checks
- [x] Numeric/absolute promotional-claim flags
- [x] Keyword-based approved-evidence retrieval
- [x] Structured finding cards with severity, source IDs and suggested action
- [x] Review state transitions and audit history
- [x] Review history and Markdown report export
- [ ] Live LLM analysis: requires a private Adaption API key in the deployment environment; never expose the key in frontend or repository
- [ ] Public hosted deployment: pending deployment and incognito verification

## Technical implementation
React + Vite frontend; FastAPI backend; SQLite local demo persistence; PyMuPDF and python-docx; optional Adaption Responses API configured for Qwen 3.5 397B. Round 1 proposed MongoDB Atlas; Round 2 uses SQLite as a disclosed simplification for a reproducible, self-contained MVP. Replace with MongoDB Atlas before production multi-user deployment.

## Changes from Round 1 plan
1. Use SQLite for the initial single-workspace demo instead of MongoDB Atlas to reduce deployment and setup risk for the solo MVP.
2. Use keyword retrieval first as explicitly allowed by the Round 1 proposal; semantic/vector retrieval remains future work.
3. Keep image/logo and accessibility checks out of Round 2 and reserve them for Round 3.
4. The initial app is a single-workspace demonstrator, not production multi-tenant software; authentication and workspace isolation are future hardening work.

## Three meaningful Round 3 improvements
1. Visual brand checks: compare uploaded creative assets with approved logos and brand colours; route uncertain matches to human review.
2. Claim provenance and expiry: add claim owner, source, effective date, expiry date and renewal status; flag expired evidence.
3. Governance insights: report recurring issue categories, channels and unclear guideline areas with review-history trends.

## Limitations and responsible use
Without an Adaption API key, the live LLM layer is disabled and the app runs deterministic rules/claim checks only; the UI and API status clearly disclose this. Missing evidence is not treated as proof a claim is false. This MVP does not provide legal certification, full factual verification, production security or autonomous publication. Do not upload confidential client documents to the demo unless authorised.
