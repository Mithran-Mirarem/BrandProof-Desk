# BrandProof Desk — Round 3 scope and verification

## Committed improvement 1: Visual Brand Compliance

User outcome: a reviewer can screen an uploaded creative asset for use of the current logo, approved brand colours and restricted text embedded in artwork.

Delivered implementation:
- Upload and persist one approved PNG/JPEG/WebP logo reference.
- Configure up to 12 approved HEX colours.
- Extract dominant colours and compare against the palette with a documented RGB-distance tolerance; neutral black/white/grey are not treated as palette violations.
- Search candidate image crops with a 64-bit difference hash for a possible logo match.
- Optional local Tesseract OCR to extract embedded text and compare it with restricted terminology.
- Persist a visual review summary, SHA-256 checksum, colours, findings and timestamp.

Verification:
- API test uploads a generated PNG and checks that analysis is persisted.
- Unit test checks an off-palette significant colour is flagged.
- Unit test checks logo-screening returns a candidate signal for a known fixture.
- Unsupported formats are rejected.

Known limitations: the logo algorithm can produce false positives/negatives, does not perform geometric/brand-guideline verification, and supports one reference logo. OCR requires Tesseract installed on the backend machine. Human review remains mandatory.

## Committed improvement 2: Evidence Provenance and Expiry

User outcome: a reviewer can understand who approved a fact, where it came from, which version is in effect and whether it is still valid.

Delivered implementation:
- SQLite evidence registry with source name/URL, owner, version, valid-from, valid-until and state.
- Evidence event log preserves creation, field/version changes and deletion; the registry can display the event history.
- Database initialisation migrates the existing Round 2 JSON evidence into the new registry.
- Backend computes effective `expired` and `scheduled` states from dates.
- Only approved, currently valid evidence is sent to local AI review.
- Related expired, scheduled or soon-to-expire evidence creates an `evidence_expiry` finding and remains visible as a lifecycle reference.
- PDF review reports include source, owner, version, URL and validity metadata.

Verification:
- CRUD API test covers evidence creation, listing, update and deletion.
- Audit test verifies events remain readable even after a record is deleted.
- Unit test checks that expired evidence is excluded from eligible retrieval.
- Unit test checks that a matching expired record appears as an expiry finding and remains visible in review evidence references.

## Committed improvement 3: Governance Analytics

User outcome: workspace administrators can find recurring content issues and understand how reviews are progressing.

Delivered implementation:
- Aggregates text and visual findings by category/severity.
- Review decisions by status and submissions by channel.
- Approval rate for text reviews, visual screening count and recurring issue labels.
- Fourteen-day activity timeline combining text reviews and visual screenings.

Verification: endpoint is exercised by the integration test; the frontend provides empty-state handling and data-driven bar/timeline displays.

## Limitations / deployment notes

- Analytics are workspace-local SQLite aggregates, not statistically normalised or predictive.
- Existing API remains unauthenticated and single-tenant; use synthetic demo content only.
- Local Ollama and the FastAPI process must run on the machine for text AI review. Visual and analytics endpoints are backend-local as well.
- When OCR is not installed, the visual module clearly reports OCR as unavailable rather than implying image text was checked.
- Visual colour/logo checks are deterministic heuristics and not certified brand verification.

## Round 3 demo sequence

1. Configure palette and approved logo.
2. Screen one creative; explain detected colours, logo candidate score and OCR status.
3. Inspect a current evidence source and an intentionally expired test record.
4. Run a text review and show the expiry warning.
5. Export the review PDF and show provenance metadata.
6. Open governance analytics and explain the current data window and limitations.
