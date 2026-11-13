import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from io import BytesIO

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load local configuration before importing modules that read environment variables.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
from . import db
from .review import run_review
from .ai import ollama_status
from .report import build_review_pdf
from .visual import analyse_creative, load_image, sha256

db.init_db()
app = FastAPI(title="BrandProof Desk API", version="0.4.0", description="Evidence-linked brand governance with visual screening and governance analytics")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])


class BrandUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    tone: str = Field(min_length=5, max_length=1500)
    required_terms: list[str] = []
    forbidden_terms: list[str] = []
    approved_facts: list[dict] = []


class ReviewRequest(BaseModel):
    content: str = Field(min_length=10, max_length=30000)
    channel: str = "Social media"
    brief: str = ""


class DecisionRequest(BaseModel):
    status: str
    note: str = ""


class DraftUpdate(BaseModel):
    revised_text: str = Field(min_length=1, max_length=30000)


class EvidenceRecord(BaseModel):
    id: str | None = Field(default=None, min_length=2, max_length=80)
    claim: str = Field(min_length=5, max_length=3000)
    source: str = Field(min_length=2, max_length=300)
    source_url: str = Field(default="", max_length=1500)
    owner: str = Field(default="Unassigned", max_length=160)
    version: str = Field(default="1.0", max_length=50)
    valid_from: str = Field(default="", max_length=10)
    valid_until: str = Field(default="", max_length=10)
    status: str = Field(default="pending_verification")

class VisualPaletteUpdate(BaseModel):
    palette: list[str] = Field(default_factory=list, max_length=12)


@app.get("/api/evidence")
def evidence_records():
    return db.list_evidence_records()


@app.get("/api/evidence/{evidence_id}/history")
def evidence_history(evidence_id: str):
    if not db.get_evidence_record(evidence_id):
        # Keep the historical log readable even after an evidence record is archived/deleted.
        history = db.get_evidence_history(evidence_id)
        if not history: raise HTTPException(404, "Evidence record and audit history not found.")
        return history
    return db.get_evidence_history(evidence_id)


@app.post("/api/evidence")
def create_evidence(payload: EvidenceRecord):
    data = payload.model_dump(exclude={"id"})
    if data["status"] not in {"approved", "pending_verification", "archived"}:
        raise HTTPException(400, "Status must be approved, pending_verification or archived.")
    try:
        for field in ("valid_from", "valid_until"):
            if data[field]: datetime.strptime(data[field], "%Y-%m-%d")
    except ValueError:
        raise HTTPException(400, "Evidence dates must use YYYY-MM-DD.")
    if data["valid_from"] and data["valid_until"] and data["valid_until"] < data["valid_from"]:
        raise HTTPException(400, "Valid-until date cannot be earlier than valid-from date.")
    if data["source_url"] and not data["source_url"].startswith(("https://", "http://")):
        raise HTTPException(400, "Source URL must start with http:// or https://.")
    if data["status"] == "approved" and (not data["source"].strip() or not data["owner"].strip() or data["owner"].strip().lower() == "unassigned"):
        raise HTTPException(400, "Approved evidence needs a named source and owner.")
    data["id"] = payload.id or f"EVD-{uuid.uuid4().hex[:8].upper()}"
    if db.get_evidence_record(data["id"]):
        raise HTTPException(409, "An evidence record with this ID already exists.")
    return db.create_evidence_record(data)


@app.put("/api/evidence/{evidence_id}")
def edit_evidence(evidence_id: str, payload: EvidenceRecord):
    data = payload.model_dump(exclude={"id"})
    if data["status"] not in {"approved", "pending_verification", "archived"}:
        raise HTTPException(400, "Status must be approved, pending_verification or archived.")
    try:
        for field in ("valid_from", "valid_until"):
            if data[field]: datetime.strptime(data[field], "%Y-%m-%d")
    except ValueError:
        raise HTTPException(400, "Evidence dates must use YYYY-MM-DD.")
    if data["valid_from"] and data["valid_until"] and data["valid_until"] < data["valid_from"]:
        raise HTTPException(400, "Valid-until date cannot be earlier than valid-from date.")
    if data["source_url"] and not data["source_url"].startswith(("https://", "http://")):
        raise HTTPException(400, "Source URL must start with http:// or https://.")
    if data["status"] == "approved" and (not data["source"].strip() or not data["owner"].strip() or data["owner"].strip().lower() == "unassigned"):
        raise HTTPException(400, "Approved evidence needs a named source and owner.")
    result = db.update_evidence_record(evidence_id, data)
    if not result: raise HTTPException(404, "Evidence record not found.")
    return result


@app.delete("/api/evidence/{evidence_id}")
def remove_evidence(evidence_id: str):
    if not db.delete_evidence_record(evidence_id): raise HTTPException(404, "Evidence record not found.")
    return {"deleted": True, "id": evidence_id}


@app.get("/api/visual/config")
def visual_config():
    return db.get_visual_config()


@app.put("/api/visual/config")
def update_visual_config(payload: VisualPaletteUpdate):
    palette=[]
    for color in payload.palette:
        color = color.strip().upper()
        if not re.fullmatch(r"#[0-9A-F]{6}", color):
            raise HTTPException(400, f"Invalid HEX colour: {color}. Use #RRGGBB.")
        if color not in palette: palette.append(color)
    return db.save_visual_palette(palette)


def _save_visual_upload(file: UploadFile, raw: bytes, prefix: str):
    if len(raw) > 8 * 1024 * 1024:
        raise HTTPException(413, "Image must be 8 MB or smaller.")
    try:
        load_image(raw)
    except ValueError as exc:
        raise HTTPException(415, str(exc))
    except Exception:
        raise HTTPException(400, "Could not decode this image. Upload a valid PNG, JPEG or WebP file.")
    extension = Path(file.filename or "image.png").suffix.lower()
    if extension not in {".png", ".jpg", ".jpeg", ".webp"}: extension = ".png"
    folder = Path(__file__).resolve().parent.parent / "uploads" / "visual"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{prefix}-{uuid.uuid4().hex}{extension}"
    target.write_bytes(raw)
    return target


@app.post("/api/visual/logo-reference")
async def upload_logo_reference(file: UploadFile = File(...)):
    raw = await file.read()
    previous = db.get_logo_reference_path()
    target = _save_visual_upload(file, raw, "logo-reference")
    config = db.set_logo_reference(str(target), Path(file.filename or target.name).name)
    if previous and previous != str(target):
        try: Path(previous).unlink(missing_ok=True)
        except OSError: pass
    return {**config, "sha256": sha256(raw)}


@app.delete("/api/visual/logo-reference")
def delete_logo_reference():
    previous = db.get_logo_reference_path()
    if previous:
        try: Path(previous).unlink(missing_ok=True)
        except OSError: pass
    return db.clear_logo_reference()


@app.post("/api/visual/reviews")
async def visual_review(file: UploadFile = File(...)):
    raw = await file.read()
    if len(raw) > 8 * 1024 * 1024: raise HTTPException(413, "Image must be 8 MB or smaller.")
    try:
        brand = db.get_brand()
        config = db.get_visual_config()
        result = analyse_creative(raw, file.filename or "creative", config.get("palette", []), db.get_logo_reference_path(), brand.get("forbidden_terms", []))
    except ValueError as exc:
        raise HTTPException(415, str(exc))
    except Exception as exc:
        raise HTTPException(400, f"Visual analysis failed: {type(exc).__name__}.")
    result.update({"id": str(uuid.uuid4()), "created_at": datetime.now(timezone.utc).isoformat()})
    db.add_visual_review(result)
    return result


@app.get("/api/visual/reviews")
def visual_review_history():
    return db.list_visual_reviews()


@app.get("/api/analytics")
def governance_analytics():
    reviews = db.list_reviews()
    visual_reviews = db.list_visual_reviews()
    category_counts, severity_counts, channel_counts, status_counts, issue_counts = {}, {}, {}, {}, {}
    daily = {}
    for review in reviews:
        status = review.get("status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        channel = review.get("channel", "Other")
        channel_counts[channel] = channel_counts.get(channel, 0) + 1
        try: day = datetime.fromisoformat(review.get("created_at", "").replace("Z", "+00:00")).date().isoformat()
        except ValueError: day = "unknown"
        daily[day] = daily.get(day, 0) + 1
        for finding in review.get("findings", []):
            category = str(finding.get("category", "other")).replace("_", " ")
            severity = finding.get("severity", "info")
            category_counts[category] = category_counts.get(category, 0) + 1
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            quote = re.sub(r"\s+", " ", str(finding.get("quote", "")).strip())[:110]
            if quote: issue_counts[quote] = issue_counts.get(quote, 0) + 1
    visual_days = {}
    for visual in visual_reviews:
        try: visual_day = datetime.fromisoformat(visual.get("created_at", "").replace("Z", "+00:00")).date().isoformat()
        except ValueError: visual_day = "unknown"
        visual_days[visual_day] = visual_days.get(visual_day, 0) + 1
        for finding in visual.get("findings", []):
            category = str(finding.get("category", "visual issue")).replace("_", " ")
            severity = finding.get("severity", "info")
            category_counts[category] = category_counts.get(category, 0) + 1
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            label = str(finding.get("title") or finding.get("details") or category)[:110]
            issue_counts[label] = issue_counts.get(label, 0) + 1
    if visual_reviews:
        channel_counts["Visual assets"] = channel_counts.get("Visual assets", 0) + len(visual_reviews)
    total = len(reviews)
    resolved = status_counts.get("approved", 0)
    days = [(datetime.now(timezone.utc).date() - timedelta(days=i)).isoformat() for i in range(13, -1, -1)]
    return {
        "summary": {"reviews": total, "findings": sum(severity_counts.values()), "approved": resolved,
                    "open": status_counts.get("in_review", 0), "changes_requested": status_counts.get("changes_requested", 0),
                    "escalated": status_counts.get("escalated", 0), "visual_reviews": len(visual_reviews),
                    "approval_rate": round((resolved / total) * 100, 1) if total else 0},
        "by_category": [{"label":k,"value":v} for k,v in sorted(category_counts.items(), key=lambda x:(-x[1],x[0]))],
        "by_severity": [{"label":k,"value":v} for k,v in sorted(severity_counts.items(), key=lambda x:(-x[1],x[0]))],
        "by_channel": [{"label":k,"value":v} for k,v in sorted(channel_counts.items(), key=lambda x:(-x[1],x[0]))],
        "by_status": [{"label":k,"value":v} for k,v in sorted(status_counts.items(), key=lambda x:(-x[1],x[0]))],
        "recurring_issues": [{"label":k,"value":v} for k,v in sorted(issue_counts.items(), key=lambda x:(-x[1],x[0]))[:8]],
        "timeline": [{"date":d,"reviews":daily.get(d,0) + visual_days.get(d,0), "visual_reviews":visual_days.get(d,0)} for d in days],
        "disclaimer": "Analytics describe records saved in this workspace. They are not a legal compliance score or a guarantee of brand compliance."
    }


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "BrandProof Desk API"}


@app.get("/api/status")
def status():
    return ollama_status()


@app.get("/api/brand")
def read_brand():
    return db.get_brand()


@app.put("/api/brand")
def update_brand(payload: BrandUpdate):
    data = payload.model_dump()
    for index, fact in enumerate(data["approved_facts"]):
        if not fact.get("id"):
            fact["id"] = f"FACT-{index + 1:03d}"
        fact.setdefault("source", "User-added approved source")
        fact.setdefault("status", "approved")
        fact.setdefault("valid_until", "")
    db.save_brand(data)
    return db.get_brand()


@app.post("/api/reviews")
def create_review(payload: ReviewRequest):
    review = run_review(payload.content, payload.channel, payload.brief, db.get_brand())
    db.add_review(review)
    return review


@app.post("/api/reviews/upload")
async def upload_review(file: UploadFile = File(...), channel: str = Form("Document"), brief: str = Form("")):
    raw = await file.read()
    if len(raw) > 8 * 1024 * 1024:
        raise HTTPException(413, "File must be 8 MB or smaller.")
    name = (file.filename or "").lower()
    try:
        if name.endswith(".pdf"):
            import fitz
            document = fitz.open(stream=raw, filetype="pdf")
            content = "\n".join(page.get_text() for page in document)
        elif name.endswith(".docx"):
            from docx import Document
            import io
            document = Document(io.BytesIO(raw))
            content = "\n".join(paragraph.text for paragraph in document.paragraphs)
        elif name.endswith(".txt"):
            content = raw.decode("utf-8-sig")
        else:
            raise HTTPException(415, "Supported formats: PDF, DOCX and TXT.")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(400, "Could not read this document. Try exporting it as PDF or DOCX.")
    if len(content.strip()) < 10:
        raise HTTPException(400, "No usable text was extracted from this file.")
    review = run_review(content, channel, brief, db.get_brand())
    review["title"] = Path(file.filename or "Uploaded document").stem[:70]
    db.add_review(review)
    return review


@app.get("/api/reviews")
def reviews():
    return db.list_reviews()


@app.get("/api/reviews/{review_id}")
def review_detail(review_id: str):
    item = db.get_review(review_id)
    if not item:
        raise HTTPException(404, "Review not found")
    item["audit"] = db.get_audit(review_id)
    return item


@app.post("/api/reviews/{review_id}/decision")
def decide(review_id: str, payload: DecisionRequest):
    allowed = {"approved", "changes_requested", "escalated"}
    if payload.status not in allowed:
        raise HTTPException(400, f"Status must be one of {sorted(allowed)}")
    item = db.get_review(review_id)
    if not item:
        raise HTTPException(404, "Review not found")
    db.update_review(review_id, status=payload.status)
    db.audit(review_id, payload.status, payload.note or f"Review status changed to {payload.status}")
    return db.get_review(review_id)


@app.post("/api/reviews/{review_id}/apply-suggestions")
def apply_suggestions(review_id: str):
    item = db.get_review(review_id)
    if not item:
        raise HTTPException(404, "Review not found")
    revised = item["revised_text"]
    if revised == item["original_text"]:
        raise HTTPException(409, "No AI-generated full-text revision is available. Edit the working revision manually or confirm that Ollama is running.")
    db.update_review(review_id, revised_text=revised)
    db.audit(review_id, "suggestion_applied", "Creator applied the AI-proposed revision; review is still required.")
    return db.get_review(review_id)


@app.put("/api/reviews/{review_id}/draft")
def save_draft(review_id: str, payload: DraftUpdate):
    item = db.get_review(review_id)
    if not item:
        raise HTTPException(404, "Review not found")
    db.update_review(review_id, revised_text=payload.revised_text)
    db.audit(review_id, "draft_edited", "Creator saved an edited working revision. Human approval is still required.")
    return db.get_review(review_id)


@app.get("/api/reviews/{review_id}/report")
def report_json(review_id: str):
    """Retain the JSON report endpoint for integrations and debugging."""
    item = db.get_review(review_id)
    if not item:
        raise HTTPException(404, "Review not found")
    return {
        "report_title": item["title"],
        "status": item["status"],
        "summary": f"{len(item['findings'])} finding(s)",
        "original_text": item["original_text"],
        "revised_text": item["revised_text"],
        "findings": item["findings"],
        "evidence": item["evidence"],
        "audit": db.get_audit(review_id),
    }


@app.get("/api/reviews/{review_id}/report.pdf")
def report_pdf(review_id: str):
    """Download a formatted, multi-page PDF review report."""
    item = db.get_review(review_id)
    if not item:
        raise HTTPException(404, "Review not found")
    item["audit"] = db.get_audit(review_id)
    pdf_bytes = build_review_pdf(item, item["audit"])
    safe_id = "".join(ch for ch in review_id if ch.isalnum() or ch in "-_ ")[:60] or "review"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="brandproof-review-{safe_id}.pdf"'},
    )
