# Round 2 scope and demonstration notes

## Required end-to-end workflow
1. A brand administrator configures a brand name, tone, exact required/restricted terms and approved fact records with source metadata.
2. A content creator submits pasted content or a PDF/DOCX/TXT file and selects channel/context.
3. The review coordinator chooses checks based on the submitted content.
4. Deterministic checks find exact restricted terminology and numeric/absolute claims that require approved evidence.
5. Keyword retrieval returns relevant approved fact records with IDs, source labels and validity dates.
6. If `ADAPTION_API_KEY` is configured, the LLM performs tone/context analysis and proposes purpose-preserving edits. Otherwise the product visibly uses the deterministic fallback.
7. Findings show category, severity, quote, explanation, evidence IDs, suggested action and confidence.
8. A human applies a revision and records approved / changes requested / escalated.
9. The history and audit log retain decisions.

## Demo input

"Our revolutionary Northstar Analytics workspace guarantees 100% customer success in just 7 days. Our platform provides dashboards and reporting to help teams understand their operations."

Expected checks: restricted terms `revolutionary` and `guaranteed results`/`guaranteed` if included in the restricted list; a 100% absolute claim flagged for approved substantiation; Northstar fact retrieval. Absence of exact supporting evidence is labelled as evidence not found, not as proof the claim is false.

## Three planned Round 3 improvements
- Visual brand checks: compare uploaded image/logo against approved assets and palette; only report supported matches and uncertainty.
- Claim provenance and expiry: add owner, source, effective date, expiry, and renewal alerts; flag claims after expiry.
- Governance insights: aggregate recurring issue categories, channel-level patterns and rules frequently triggering questions; show where guidelines may be unclear.
