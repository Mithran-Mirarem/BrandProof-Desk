"""PDF report rendering for BrandProof Desk reviews."""
from __future__ import annotations

from datetime import datetime
from html import escape
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _register_font() -> str:
    """Register a commonly available Unicode font; fall back to built-in Helvetica."""
    candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/calibri.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
    ]
    for path in candidates:
        if path.exists():
            try:
                if "BrandProofUnicode" not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont("BrandProofUnicode", str(path)))
                return "BrandProofUnicode"
            except Exception:
                continue
    return "Helvetica"


def _safe_text(value) -> str:
    text = str(value or "")
    # Drop control characters that can break PDF paragraph parsing.
    text = "".join(ch for ch in text if ch in "\n\t" or ord(ch) >= 32)
    return escape(text).replace("\n", "<br/>").replace("\t", "&nbsp;&nbsp;&nbsp;&nbsp;")


def _paragraph(text, style):
    return Paragraph(_safe_text(text), style)


def build_review_pdf(review: dict, audit: list[dict] | None = None) -> bytes:
    """Build a readable multi-page PDF containing the review and governance trail."""
    font_name = _register_font()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"BrandProof Desk Review - {review.get('title', 'Review')}",
        author="BrandProof Desk",
        subject="Evidence-linked brand governance review",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="BPTitle", parent=styles["Title"], fontName=font_name,
        fontSize=19, leading=24, textColor=colors.HexColor("#13243A"),
        alignment=TA_CENTER, spaceAfter=5 * mm,
    ))
    styles.add(ParagraphStyle(
        name="BPSub", parent=styles["Normal"], fontName=font_name,
        fontSize=8.5, leading=12, textColor=colors.HexColor("#53657A"),
        alignment=TA_CENTER, spaceAfter=5 * mm,
    ))
    styles.add(ParagraphStyle(
        name="BPHeading", parent=styles["Heading2"], fontName=font_name,
        fontSize=12, leading=16, textColor=colors.HexColor("#1E4C83"),
        spaceBefore=4 * mm, spaceAfter=2 * mm,
    ))
    styles.add(ParagraphStyle(
        name="BPBody", parent=styles["BodyText"], fontName=font_name,
        fontSize=8.5, leading=12.5, textColor=colors.HexColor("#243447"),
        spaceAfter=2 * mm, splitLongWords=1,
    ))
    styles.add(ParagraphStyle(
        name="BPSmall", parent=styles["BodyText"], fontName=font_name,
        fontSize=7.5, leading=10, textColor=colors.HexColor("#53657A"),
        spaceAfter=1.5 * mm,
    ))
    styles.add(ParagraphStyle(
        name="BPFinding", parent=styles["BodyText"], fontName=font_name,
        fontSize=8, leading=11.5, textColor=colors.HexColor("#243447"),
        spaceAfter=1.2 * mm,
    ))

    story = [
        _paragraph("BrandProof Desk", styles["BPTitle"]),
        _paragraph("Evidence-linked brand governance review", styles["BPSub"]),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#D8E2EF"), spaceAfter=4 * mm),
    ]

    created = review.get("created_at", "")
    try:
        created_display = datetime.fromisoformat(created.replace("Z", "+00:00")).astimezone().strftime("%d %b %Y, %I:%M %p %Z")
    except Exception:
        created_display = created or "Not available"

    meta_rows = [
        ["Review ID", review.get("id", ""), "Status", str(review.get("status", "in_review")).replace("_", " ").title()],
        ["Channel", review.get("channel", ""), "Submitted", created_display],
        ["AI mode", review.get("agent_mode", "unknown"), "Findings", str(len(review.get("findings") or []))],
    ]
    meta = Table(meta_rows, colWidths=[24 * mm, 58 * mm, 23 * mm, 69 * mm])
    meta.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F3F7FC")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#1E4C83")),
        ("TEXTCOLOR", (2, 0), (2, -1), colors.HexColor("#1E4C83")),
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D8E2EF")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([meta, Spacer(1, 4 * mm)])

    story.append(_paragraph("Review summary", styles["BPHeading"]))
    story.append(_paragraph(review.get("summary") or "No summary supplied.", styles["BPBody"]))

    story.append(_paragraph("Submitted content", styles["BPHeading"]))
    story.append(_paragraph(review.get("original_text") or "No submitted content.", styles["BPBody"]))

    story.append(_paragraph(f"Findings ({len(review.get('findings') or [])})", styles["BPHeading"]))
    findings = review.get("findings") or []
    if not findings:
        story.append(_paragraph("No findings were raised by the configured checks. This is not a guarantee of complete brand compliance.", styles["BPBody"]))
    for index, finding in enumerate(findings, start=1):
        severity = str(finding.get("severity", "info")).upper()
        title = f"{index}. [{severity}] {finding.get('category', 'Finding')}"
        evidence_ids = finding.get("evidence_ids") or []
        parts = [
            _paragraph(title, styles["BPFinding"]),
            _paragraph(f"Quoted content: {finding.get('quote', '')}", styles["BPSmall"]),
            _paragraph(f"Explanation: {finding.get('explanation', '')}", styles["BPFinding"]),
            _paragraph(f"Evidence: {', '.join(evidence_ids) if evidence_ids else 'No approved evidence matched; human verification required.'}", styles["BPSmall"]),
            _paragraph(f"Suggested correction: {finding.get('suggestion', '') or 'No suggestion provided.'}", styles["BPFinding"]),
            Spacer(1, 1.5 * mm),
            HRFlowable(width="100%", thickness=0.35, color=colors.HexColor("#E1E8F0"), spaceAfter=2 * mm),
        ]
        story.extend(parts)

    story.append(_paragraph("Evidence references and lifecycle status", styles["BPHeading"]))
    evidence = review.get("evidence") or []
    if evidence:
        for item in evidence:
            story.append(_paragraph(
                f"{item.get('id', 'SOURCE')} — {item.get('claim', '')}\nSource: {item.get('source', 'Not specified')} | Owner: {item.get('owner', 'Not specified')} | Version: {item.get('version', 'Not specified')}\nSource URL: {item.get('source_url', 'Not supplied')} | Valid from: {item.get('valid_from', 'Not specified')} | Valid until: {item.get('valid_until', 'Not specified')} | State: {item.get('status', 'unknown')}",
                styles["BPSmall"],
            ))
    else:
        story.append(_paragraph("No approved evidence records were attached to this review.", styles["BPBody"]))

    story.append(_paragraph("Suggested revision", styles["BPHeading"]))
    story.append(_paragraph(review.get("revised_text") or "No revised text was generated.", styles["BPBody"]))

    story.append(_paragraph("Human decision and audit history", styles["BPHeading"]))
    if audit:
        for event in audit:
            story.append(_paragraph(
                f"{str(event.get('event', 'event')).replace('_', ' ').title()} — {event.get('detail', '')}\n{event.get('created_at', '')}",
                styles["BPSmall"],
            ))
    else:
        story.append(_paragraph("No reviewer decision or audit events have been recorded yet.", styles["BPBody"]))

    story.append(Spacer(1, 3 * mm))
    story.append(_paragraph(
        "Generated by BrandProof Desk. Findings are advisory. An authorised human reviewer must make the final publication decision.",
        styles["BPSmall"],
    ))

    def add_page_number(canvas, document):
        canvas.saveState()
        canvas.setFont(font_name, 7)
        canvas.setFillColor(colors.HexColor("#718096"))
        canvas.drawString(18 * mm, 10 * mm, "BrandProof Desk · Evidence before judgement")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    return buffer.getvalue()
