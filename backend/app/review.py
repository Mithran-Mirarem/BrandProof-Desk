"""Evidence-grounded brand review with local Ollama analysis and finding consolidation."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher

from .ai import ollama_analyze

CLAIM_PATTERNS = [
    r"\bguarantee[sd]?\b",
    r"\b\d{1,3}(?:\.\d+)?\s?%(?!\w)",
    r"\b(100%|double|triple|zero risk|risk-free|number one|no\.\s?1)(?!\w)",
    r"\b(increase|boost|improve|save|reduce)\b.{0,45}\b\d+\s?%\b",
]
SEVERITY_RANK = {"info": 0, "warning": 1, "critical": 2}
CATEGORY_FAMILY = {
    "promotional_claim": "promotional_claim",
    "promotional_claim_review": "promotional_claim",
    "claim_review": "promotional_claim",
    "claim_substantiation": "promotional_claim",
    "tone_and_message_review": "tone_and_message",
    "tone_review": "tone_and_message",
    "brand_tone": "tone_and_message",
    "terminology": "terminology",
    "brand_naming": "brand_naming",
    "evidence_retrieval": "evidence_retrieval",
}


def _normalise(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (value or "").lower()))


def _token_similarity(left: str, right: str) -> float:
    a = set(_normalise(left).split())
    b = set(_normalise(right).split())
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def _same_underlying_issue(first: dict, second: dict) -> bool:
    first_family = CATEGORY_FAMILY.get(first.get("category", ""), first.get("category", ""))
    second_family = CATEGORY_FAMILY.get(second.get("category", ""), second.get("category", ""))
    if first_family != second_family:
        return False
    left = _normalise(first.get("quote", ""))
    right = _normalise(second.get("quote", ""))
    if not left or not right:
        return False
    if left == right or left in right or right in left:
        return True
    return _token_similarity(left, right) >= 0.78


def _is_supported_fact_finding(item: dict, evidence: list[dict]) -> bool:
    """Suppress evidence-retrieval info items that merely restate an approved fact."""
    category = (item.get("category") or "").lower()
    # Informational comments that quote an approved fact verbatim are not issues,
    # even if the model labels the comment as tone, context, or evidence review.
    if (item.get("severity") or "info").lower() != "info":
        return False
    quote = _normalise(item.get("quote", ""))
    if not quote:
        return False
    cited = set(item.get("evidence_ids") or [])
    for fact in evidence:
        fact_id = fact.get("id")
        if cited and fact_id not in cited:
            continue
        claim = _normalise(fact.get("claim", ""))
        if not claim:
            continue
        # Exact match or a near-exact token match is treated as supported, not as a finding.
        if quote == claim or (len(quote.split()) >= 5 and _token_similarity(quote, claim) >= 0.88):
            return True
    return False


def _finding(category, severity, quote, explanation, evidence_ids=None, suggestion="", confidence="high", source="rule_engine"):
    severity = severity if severity in SEVERITY_RANK else "warning"
    confidence = confidence if confidence in {"low", "medium", "high"} else "medium"
    return {
        "id": str(uuid.uuid4())[:8],
        "category": category,
        "severity": severity,
        "quote": str(quote or "")[:500],
        "explanation": str(explanation or ""),
        "evidence_ids": list(dict.fromkeys(evidence_ids or [])),
        "suggestion": str(suggestion or ""),
        "confidence": confidence,
        "source": source,
        "action": "open",
    }


def _relevant_evidence(text, facts, tone):
    words = set(re.findall(r"[a-zA-Z0-9]{4,}", text.lower()))
    ranked = []
    for fact in facts:
        if fact.get("status", "approved") != "approved":
            continue
        ftext = fact.get("claim", "")
        tokens = set(re.findall(r"[a-zA-Z0-9]{4,}", ftext.lower()))
        score = len(words & tokens)
        if score > 0:
            ranked.append((score, fact))
    ranked.sort(key=lambda x: x[0], reverse=True)
    return [fact for _, fact in ranked[:8]] or [f for f in facts if f.get("status", "approved") == "approved"][:5]


def _relevant_lapsed_evidence(text, facts):
    """Find records whose wording overlaps the draft but are expired or not yet valid."""
    words = set(re.findall(r"[a-zA-Z0-9]{4,}", text.lower()))
    ranked = []
    for fact in facts:
        if fact.get("status") not in {"expired", "scheduled"} and not fact.get("expires_soon"):
            continue
        tokens = set(re.findall(r"[a-zA-Z0-9]{4,}", str(fact.get("claim", "")).lower()))
        score = len(words & tokens)
        if score >= 2:
            ranked.append((score, fact))
    ranked.sort(key=lambda x: x[0], reverse=True)
    return [fact for _, fact in ranked[:5]]


def _consolidate_findings(findings: list[dict]) -> list[dict]:
    """Merge overlapping findings from rules and the LLM without hiding distinct issue types."""
    consolidated: list[dict] = []
    for incoming in findings:
        existing = next((current for current in consolidated if _same_underlying_issue(current, incoming)), None)
        if existing is None:
            consolidated.append(incoming)
            continue

        if SEVERITY_RANK.get(incoming.get("severity", "info"), 0) > SEVERITY_RANK.get(existing.get("severity", "info"), 0):
            existing["severity"] = incoming["severity"]
        if len(incoming.get("quote", "")) > len(existing.get("quote", "")):
            existing["quote"] = incoming["quote"]
        for key in ("explanation", "suggestion"):
            current_text = (existing.get(key) or "").strip()
            incoming_text = (incoming.get(key) or "").strip()
            if incoming_text and incoming_text not in current_text:
                existing[key] = (current_text + " " + incoming_text).strip() if current_text else incoming_text
        existing["evidence_ids"] = list(dict.fromkeys((existing.get("evidence_ids") or []) + (incoming.get("evidence_ids") or [])))
        confidence_rank = {"low": 0, "medium": 1, "high": 2}
        if confidence_rank.get(incoming.get("confidence", "low"), 0) > confidence_rank.get(existing.get("confidence", "low"), 0):
            existing["confidence"] = incoming["confidence"]
        if existing.get("category") in {"promotional_claim", "promotional_claim_review", "claim_review", "claim_substantiation"}:
            existing["category"] = "promotional_claim"
        if existing.get("category") in {"tone_review", "brand_tone", "tone_and_message_review"}:
            existing["category"] = "tone_and_message_review"
        sources = {existing.get("source", ""), incoming.get("source", "")}
        existing["source"] = "combined" if len(sources) > 1 else existing.get("source", "rule_engine")
    return consolidated


def run_review(content: str, channel: str, brief: str, brand: dict):
    findings = []
    lower = content.lower()
    checks = ["exact_terminology"]
    if any(re.search(pattern, content, re.I) for pattern in CLAIM_PATTERNS):
        checks.append("promotional_claim_review")
    if len(content.split()) > 8:
        checks.append("tone_and_message_review")
    checks.append("evidence_retrieval")
    evidence = _relevant_evidence(content, brand["approved_facts"], brand["tone"])
    evidence_ids = [item["id"] for item in evidence if item.get("id")]
    lapsed_evidence = _relevant_lapsed_evidence(content, brand["approved_facts"])
    for item in lapsed_evidence:
        state = item.get("status", "expired")
        timing = "expires within 30 days" if item.get("expires_soon") and state == "approved" else ("expired" if state == "expired" else "not yet valid")
        findings.append(_finding(
            "evidence_expiry", "warning", item.get("claim", "")[:220],
            f"A related evidence record ({item.get('id', 'unknown')}) {timing}. Verify the source owner and renewal timeline before relying on this claim.",
            [item.get("id")] if item.get("id") else [],
            "Verify the source and renew or replace the record before its validity window closes.",
            "high", "evidence_lifecycle",
        ))

    for term in brand["forbidden_terms"]:
        if term.strip() and term.lower() in lower:
            findings.append(_finding(
                "terminology", "warning", term,
                f"This phrase appears in the brand's restricted terminology list. Brand tone guidance: {brand['tone']}",
                ["BRAND-RULES"], f"Replace '{term}' with precise, approved wording.", source="rule_engine",
            ))

    for term in brand["required_terms"]:
        if term.strip() and term.lower() not in lower and term.lower() == brand["name"].lower():
            findings.append(_finding(
                "brand_naming", "info", term,
                f"The approved brand name '{term}' is not present. Confirm whether this channel requires an explicit brand mention.",
                ["BRAND-RULES"], f"Consider including '{term}' where appropriate.", source="rule_engine",
            ))

    for match in re.finditer(r"[^.!?\n]+[.!?]?", content):
        sentence = match.group(0).strip()
        if not sentence:
            continue
        if any(re.search(pattern, sentence, re.I) for pattern in CLAIM_PATTERNS):
            supporting = []
            sentence_numbers = re.findall(r"\d+(?:\.\d+)?\s?%", sentence.lower())
            for fact in evidence:
                fact_text = fact.get("claim", "").lower()
                if sentence_numbers and any(number in fact_text for number in sentence_numbers):
                    supporting.append(fact.get("id"))
            findings.append(_finding(
                "promotional_claim",
                "critical" if re.search(r"guarantee|100%|zero risk|risk-free", sentence, re.I) else "warning",
                sentence,
                "This statement contains a quantified or absolute promotional claim. The approved evidence set does not substantiate the specific promise; human verification is required.",
                supporting,
                "Replace the absolute promise with a measurable, approved product capability, or attach an authorised source supporting the exact claim.",
                "high" if not supporting else "medium",
                "rule_engine",
            ))

    ai_result = ollama_analyze(content, channel, brief, brand, evidence, checks)
    ai_used = bool(ai_result and not ai_result.get("_error"))
    if ai_used:
        for item in ai_result.get("findings", [])[:16]:
            if not isinstance(item, dict) or _is_supported_fact_finding(item, evidence):
                continue
            category = str(item.get("category") or "brand_consistency")[:80]
            severity = item.get("severity", "warning")
            if severity not in SEVERITY_RANK:
                severity = "warning"
            refs = [ref for ref in item.get("evidence_ids", []) if ref in evidence_ids or ref == "BRAND-RULES"]
            findings.append(_finding(
                category, severity, item.get("quote", ""), item.get("explanation", ""),
                refs, item.get("suggestion", ""), item.get("confidence", "medium"), "ollama_local",
            ))

    unique = _consolidate_findings(findings)
    revised = (ai_result or {}).get("revised_text") or content
    mode = "local_ollama" if ai_used else "rules_fallback"
    finding_count = len(unique)

    # Generate the summary from final consolidated findings,
    # never from an independently generated LLM summary.
    if not ai_used:
        if ai_result and ai_result.get("_error"):
            summary = (
                f"Local AI was unavailable ({ai_result['_error']}). "
                f"Deterministic checks completed and identified {finding_count} finding(s). "
                "Human review is required."
            )
        else:
            summary = (
                f"Deterministic brand checks identified {finding_count} finding(s). "
                "AI-assisted analysis was not active; human review is required."
            )
    elif finding_count == 0:
        summary = (
            "No configured checks detected an issue (0 findings). "
            "This is not a guarantee of complete brand compliance."
        )
    else:
        categories = sorted({
            str(item.get("category") or "brand issue").replace("_", " ").strip()
            for item in unique
        })
        category_text = ", ".join(categories[:4])

        summary = (
            f"The review identified {finding_count} finding(s), including {category_text}. "
            "Review the supporting evidence and suggested corrections before making "
            "a publication decision."
        )
    now = datetime.now(timezone.utc).isoformat()
    evidence_for_report = {item.get("id"): item for item in evidence if item.get("id")}
    for item in lapsed_evidence:
        if item.get("id"):
            evidence_for_report[item["id"]] = item
    return {
        "id": str(uuid.uuid4()),
        "title": content.strip().splitlines()[0][:70] if content.strip() else "Untitled review",
        "channel": channel,
        "brief": brief,
        "original_text": content,
        "revised_text": revised,
        "status": "in_review",
        "findings": unique,
        "agent_mode": mode,
        "agent_plan": checks,
        # Active evidence is supplied to the model; expired/scheduled evidence is only
        # attached after analysis so it can be displayed as a lifecycle warning.
        "evidence": list(evidence_for_report.values()),
        "summary": summary,
        "created_at": now,
        "updated_at": now,
    }
