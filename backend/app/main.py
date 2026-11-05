import os
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

db.init_db()
app = FastAPI(title="BrandProof Desk API", version="0.3.0", description="Evidence-linked agentic brand governance MVP")
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
