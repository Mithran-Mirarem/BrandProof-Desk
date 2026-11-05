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
