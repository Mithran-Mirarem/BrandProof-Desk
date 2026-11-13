from datetime import date, timedelta
from io import BytesIO

from PIL import Image, ImageDraw

from app import db
from app.visual import analyse_creative, compare_palette, dominant_colors, logo_candidate_score, load_image


def test_evidence_registry_keeps_provenance_and_computes_expiry(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "round3.sqlite"))
    db.init_db()
    expired = db.create_evidence_record({
        "id": "EVD-OLD", "claim": "A legacy approved claim for a test", "source": "Source archive",
        "source_url": "https://example.com/archive", "owner": "Brand team", "version": "1.0",
        "valid_from": "2024-01-01", "valid_until": "2025-01-01", "status": "approved",
    })
    current = db.create_evidence_record({
        "id": "EVD-CURRENT", "claim": "A current approved claim for a test", "source": "Current policy",
        "source_url": "https://example.com/policy", "owner": "Legal", "version": "2.1",
        "valid_from": "2026-01-01", "valid_until": "2099-12-31", "status": "approved",
    })
    assert expired["status"] == "expired"
    assert expired["source_status"] == "approved"
    assert current["status"] == "approved"
    assert current["owner"] == "Legal"
    assert db.update_evidence_record("EVD-CURRENT", {
        "claim": "Updated current approved claim for a test", "source": "Updated policy", "source_url": "",
        "owner": "Compliance", "version": "2.2", "valid_from": "2026-01-01", "valid_until": "2099-12-31", "status": "approved",
    })["version"] == "2.2"
    audit = db.get_evidence_history("EVD-CURRENT")
    assert [event["event"] for event in audit] == ["updated", "created"]
    assert "version" in audit[0]["detail"]
    assert db.delete_evidence_record("EVD-OLD") is True
    assert db.get_evidence_history("EVD-OLD")[0]["event"] == "deleted"
    assert db.get_evidence_record("EVD-OLD") is None


def test_palette_check_detects_off_brand_significant_colour():
    result = compare_palette([
        {"hex": "#FF0000", "rgb": [255, 0, 0], "share": 0.6},
        {"hex": "#FFFFFF", "rgb": [255, 255, 255], "share": 0.4},
    ], ["#0B1F3A", "#16A6A1"])
    assert result["configured"] is True
    assert result["status"] == "review_required"
    assert result["off_palette"]


def test_visual_analysis_reports_logo_candidate_and_palette(tmp_path, monkeypatch):
    # Use a high-contrast local fixture; OCR is separately optional and deterministic here.
    logo = Image.new("RGB", (160, 80), "white")
    draw = ImageDraw.Draw(logo)
    draw.rectangle((10, 10, 65, 70), fill="#163A70")
    draw.ellipse((85, 10, 150, 75), fill="#20A080")
    logo_path = tmp_path / "brand-logo.png"
    logo.save(logo_path, format="PNG")
    creative = Image.new("RGB", (640, 360), "#163A70")
    creative.paste(logo.resize((160, 80)), (420, 250))
    stream = BytesIO(); creative.save(stream, format="PNG")
    monkeypatch.setattr("app.visual.extract_ocr_text", lambda image: ("", "OCR unavailable in test"))
    result = analyse_creative(stream.getvalue(), "campaign.png", ["#163A70", "#20A080"], str(logo_path), ["guaranteed results"])
    assert result["width"] == 640
    assert result["sha256"]
    assert result["palette_check"]["configured"]
    logo_findings = [item for item in result["findings"] if item["category"] == "logo_compliance"]
    assert logo_findings
    assert logo_findings[0]["similarity"] >= 0.78
    assert "Human verification" in result["disclaimer"]


def test_visual_loader_rejects_svg_and_unsupported_formats():
    try:
        load_image(b"<svg xmlns='http://www.w3.org/2000/svg'></svg>")
    except Exception:
        pass
    else:
        raise AssertionError("Unsupported vector image should be rejected")


def test_round3_api_endpoints_with_test_client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app import main

    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "api.sqlite"))
    db.init_db()
    client = TestClient(main.app)

    created = client.post("/api/evidence", json={
        "claim": "The current product supports controlled dashboard exports.",
        "source": "Product facts v2.0", "source_url": "https://example.com/facts",
        "owner": "Product team", "version": "2.0", "valid_from": "2026-01-01",
        "valid_until": "2099-12-31", "status": "approved",
    })
    assert created.status_code == 200
    evidence_id = created.json()["id"]
    assert created.json()["owner"] == "Product team"
    assert any(item["id"] == evidence_id for item in client.get("/api/evidence").json())
    assert client.get(f"/api/evidence/{evidence_id}/history").json()[0]["event"] == "created"

    palette = client.put("/api/visual/config", json={"palette": ["#102030", "#ABCDEF"]})
    assert palette.status_code == 200
    assert palette.json()["palette"] == ["#102030", "#ABCDEF"]
    assert client.put("/api/visual/config", json={"palette": ["not-a-hex"]}).status_code == 400

    stream = BytesIO()
    logo = Image.new("RGB", (240, 120), "white")
    draw = ImageDraw.Draw(logo)
    draw.rectangle((12, 12, 98, 108), fill="#102030")
    draw.ellipse((128, 18, 225, 112), fill="#ABCDEF")
    logo.save(stream, format="PNG")
    raw_logo = stream.getvalue()
    reference = client.post("/api/visual/logo-reference", files={"file": ("official-logo.png", raw_logo, "image/png")})
    assert reference.status_code == 200
    assert reference.json()["has_logo_reference"] is True

    visual = client.post("/api/visual/reviews", files={"file": ("test-creative.png", raw_logo, "image/png")})
    assert visual.status_code == 200
    assert visual.json()["dominant_colors"]
    assert visual.json()["sha256"]
    assert any(item["category"] == "logo_compliance" and item.get("similarity", 0) >= 0.78 for item in visual.json()["findings"])
    saved_visual = client.get("/api/visual/reviews").json()[0]
    assert saved_visual["filename"] == "test-creative.png"
    assert saved_visual["sha256"] == visual.json()["sha256"]
    assert saved_visual["width"] == 240

    analytics = client.get("/api/analytics").json()
    assert analytics["summary"]["visual_reviews"] == 1
    assert any(row["label"] == "logo compliance" for row in analytics["by_category"])
    assert client.delete("/api/visual/logo-reference").json()["has_logo_reference"] is False
    assert client.delete(f"/api/evidence/{evidence_id}").json()["deleted"] is True
    assert client.get(f"/api/evidence/{evidence_id}/history").json()[0]["event"] == "deleted"


def test_review_surfaces_matching_expired_evidence_as_lifecycle_finding(monkeypatch):
    from app.review import run_review
    content = "Northstar Analytics provides dashboard insights for our customers."
    brand = {
        "name": "Northstar Analytics", "tone": "Clear and evidence-led.",
        "required_terms": ["Northstar Analytics"], "forbidden_terms": [],
        "approved_facts": [{"id": "EVD-OLD", "claim": "Northstar Analytics provides dashboard insights for our customers.",
                            "source": "Old product facts", "owner": "Brand", "version": "1.0",
                            "valid_until": "2025-01-01", "status": "expired"}],
    }
    monkeypatch.setattr("app.review.ollama_analyze", lambda *args, **kwargs: None)
    result = run_review(content, "Website", "", brand)
    expiry = [f for f in result["findings"] if f["category"] == "evidence_expiry"]
    assert expiry
    assert "EVD-OLD" in expiry[0]["evidence_ids"]
    assert any(item["id"] == "EVD-OLD" and item["status"] == "expired" for item in result["evidence"])


def test_pdf_report_build_includes_provenance_fields():
    from app.report import build_review_pdf
    review = {
        "id": "r3-test", "title": "Report test", "status": "in_review", "channel": "Website",
        "created_at": "2026-11-11T10:00:00+00:00", "agent_mode": "rules_fallback",
        "summary": "One lifecycle finding.", "original_text": "Example submitted draft.",
        "revised_text": "Example revised draft.", "findings": [],
        "evidence": [{"id":"EVD-1", "claim":"Supported claim used for the report.", "source":"Product source",
                      "owner":"Product team", "version":"2.3", "source_url":"https://example.com/source",
                      "valid_from":"2026-01-01", "valid_until":"2027-01-01", "status":"approved"}],
    }
    pdf = build_review_pdf(review, [])
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 1000
