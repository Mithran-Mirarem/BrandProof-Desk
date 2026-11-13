from app.review import run_review

BRAND={
 "name":"Northstar Analytics",
 "tone":"Professional, clear, confident and evidence-led. Avoid hype and absolute guarantees.",
 "required_terms":["Northstar Analytics"],
 "forbidden_terms":["revolutionary","guaranteed results","100% success"],
 "approved_facts":[
  {"id":"FACT-001","claim":"Northstar Analytics provides dashboards and reporting.","source":"Product facts v1.2","valid_until":"2027-12-31","status":"approved"},
  {"id":"POLICY-003","claim":"Do not promise guaranteed outcomes.","source":"Claims policy v1.0","valid_until":"2027-12-31","status":"approved"}
 ]
}

def test_flags_restricted_phrase_and_absolute_claim():
    result=run_review("Our revolutionary Northstar Analytics tool guarantees 100% success in seven days.","Social media","B2B launch",BRAND)
    categories={x["category"] for x in result["findings"]}
    assert "terminology" in categories
    assert "promotional_claim" in categories
    assert result["agent_mode"] in {"rules_fallback","adaption_ai","local_ollama"}

def test_review_includes_source_records():
    result=run_review("Northstar Analytics provides dashboards and reporting for operations teams.","Website","Product overview",BRAND)
    assert len(result["evidence"]) > 0
    assert all("id" in item and "source" in item for item in result["evidence"])

def test_positive_summary_matches_zero_final_findings(monkeypatch):
    content = (
        "Northstar Analytics provides dashboards, reporting and workflow insights. "
        "Customer outcomes vary by organisation, data quality and implementation."
    )

    def fake_ollama_analyze(*args, **kwargs):
        return {
            "findings": [],
            "revised_text": content,
            "summary": "A minor informational finding was raised.",
        }

    monkeypatch.setattr(
        "app.review.ollama_analyze",
        fake_ollama_analyze
    )

    result = run_review(content, "Social media", "B2B launch", BRAND)

    assert len(result["findings"]) == 0
    assert "0 findings" in result["summary"]
    assert "minor informational finding" not in result["summary"].lower()


def test_negative_summary_count_matches_final_findings(monkeypatch):
    content = (
        "Northstar Analytics is a revolutionary analytics platform that "
        "guarantees 100% success in just seven days. "
        "It is the best in the world and delivers guaranteed results for every customer."
    )

    def fake_ollama_analyze(*args, **kwargs):
        return {
            "findings": [],
            "revised_text": content,
            "summary": "No issues detected.",
        }

    monkeypatch.setattr(
        "app.review.ollama_analyze",
        fake_ollama_analyze
    )

    result = run_review(content, "Social media", "B2B launch", BRAND)

    count = len(result["findings"])

    assert count > 0
    assert f"identified {count} finding(s)" in result["summary"]
    assert "No issues detected" not in result["summary"]



def test_expired_evidence_is_not_eligible_for_retrieval():
    from app.review import _relevant_evidence
    facts = [
        {"id": "OLD-001", "claim": "Northstar Analytics includes dashboards", "source": "Old source", "status": "expired", "valid_until": "2025-01-01"},
        {"id": "FACT-NEW", "claim": "Northstar Analytics includes dashboards and reporting", "source": "Current source", "status": "approved", "valid_until": "2099-12-31"},
    ]
    selected = _relevant_evidence("Northstar Analytics includes dashboards and reporting for teams", facts, "clear")
    assert "OLD-001" not in {x["id"] for x in selected}
    assert "FACT-NEW" in {x["id"] for x in selected}
