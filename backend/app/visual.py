"""Deterministic, explainable visual checks for BrandProof Desk.

Logo similarity is a candidate signal (perceptual hash), not an identity proof.
A human must confirm uncertain matches before publication.
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

MAX_IMAGE_PIXELS = 24_000_000
ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP"}


def load_image(raw: bytes) -> Image.Image:
    import io
    image = Image.open(io.BytesIO(raw))
    if image.format not in ALLOWED_FORMATS:
        raise ValueError("Supported image formats are PNG, JPEG and WebP.")
    if image.width * image.height > MAX_IMAGE_PIXELS:
        raise ValueError("Image dimensions are too large. Maximum is 24 megapixels.")
    image = ImageOps.exif_transpose(image).convert("RGBA")
    background = Image.new("RGBA", image.size, "white")
    background.alpha_composite(image)
    return background.convert("RGB")


def dominant_colors(image: Image.Image, limit: int = 6) -> list[dict[str, Any]]:
    thumb = image.copy()
    thumb.thumbnail((420, 420))
    quantized = thumb.convert("RGB").quantize(colors=limit, method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette() or []
    total = max(1, thumb.width * thumb.height)
    result = []
    for count, index in quantized.getcolors(total) or []:
        base = index * 3
        rgb = palette[base:base + 3]
        if len(rgb) == 3:
            result.append({"hex": "#%02X%02X%02X" % tuple(rgb), "rgb": rgb, "share": round(count / total, 3)})
    return sorted(result, key=lambda item: item["share"], reverse=True)


def _rgb(value: str) -> tuple[int, int, int] | None:
    value = (value or "").strip().lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    if len(value) != 6:
        return None
    try:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


def compare_palette(colors: list[dict], approved: list[str]) -> dict:
    refs = [(color, _rgb(color)) for color in approved]
    refs = [(color, rgb) for color, rgb in refs if rgb]
    if not refs:
        return {"configured": False, "status": "not_configured", "matches": [], "message": "No approved brand palette configured."}
    matches = []
    for color in colors:
        rgb = tuple(color["rgb"])
        nearest = min(refs, key=lambda item: sum((rgb[i] - item[1][i]) ** 2 for i in range(3)) ** 0.5)
        distance = round(sum((rgb[i] - nearest[1][i]) ** 2 for i in range(3)) ** 0.5, 1)
        is_neutral = max(rgb) - min(rgb) <= 18 or min(rgb) >= 238 or max(rgb) <= 24
        matches.append({"detected": color["hex"], "share": color["share"], "nearest_approved": nearest[0], "rgb_distance": distance, "is_neutral": is_neutral, "within_tolerance": distance <= 72 or is_neutral})
    significant_off_palette = [item for item in matches if item["share"] >= 0.04 and not item["within_tolerance"]]
    return {
        "configured": True,
        "status": "review_required" if significant_off_palette else "within_tolerance",
        "matches": matches,
        "off_palette": significant_off_palette,
        "message": f"{len(significant_off_palette)} significant detected colour(s) are outside the configured RGB tolerance." if significant_off_palette else "Detected dominant colours are within the configured RGB tolerance.",
    }


def _dhash(image: Image.Image) -> int:
    gray = ImageOps.grayscale(image).resize((9, 8), Image.Resampling.LANCZOS)
    pixels = list(gray.tobytes())
    value = 0
    for y in range(8):
        for x in range(8):
            value = (value << 1) | int(pixels[y * 9 + x] > pixels[y * 9 + x + 1])
    return value


def logo_candidate_score(creative: Image.Image, reference: Image.Image) -> float:
    """Search a handful of proportional crops for a likely logo match."""
    creative = creative.copy()
    creative.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
    ref_ratio = reference.width / max(1, reference.height)
    target = _dhash(reference)
    best = 0.0
    # Search a range of logo sizes while respecting the reference aspect ratio.
    for fraction in (0.12, 0.18, 0.25, 0.35, 0.48, 0.62, 0.78, 1.0):
        crop_h = max(32, int(creative.height * fraction))
        crop_w = max(32, int(crop_h * ref_ratio))
        if crop_w > creative.width or crop_h > creative.height:
            continue
        step_x = max(8, crop_w // 4)
        step_y = max(8, crop_h // 4)
        xs = list(range(0, max(1, creative.width - crop_w + 1), step_x))
        ys = list(range(0, max(1, creative.height - crop_h + 1), step_y))
        if not xs or xs[-1] != creative.width - crop_w: xs.append(creative.width - crop_w)
        if not ys or ys[-1] != creative.height - crop_h: ys.append(creative.height - crop_h)
        for y in ys:
            for x in xs:
                crop = creative.crop((x, y, x + crop_w, y + crop_h))
                similarity = 1.0 - ((_dhash(crop) ^ target).bit_count() / 64)
                if similarity > best:
                    best = similarity
    return round(best, 3)


def extract_ocr_text(image: Image.Image) -> tuple[str, str]:
    if not shutil.which("tesseract"):
        return "", "OCR unavailable: install the Tesseract OCR engine to inspect embedded image text."
    try:
        import pytesseract
        text = pytesseract.image_to_string(image).strip()
        return text[:12000], "OCR completed using local Tesseract." if text else "OCR ran, but no readable text was detected."
    except Exception as exc:
        return "", f"OCR unavailable: {type(exc).__name__}."


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def analyse_creative(raw: bytes, filename: str, approved_palette: list[str], logo_reference_path: str, forbidden_terms: list[str]) -> dict:
    image = load_image(raw)
    colors = dominant_colors(image)
    palette_result = compare_palette(colors, approved_palette)
    ocr_text, ocr_message = extract_ocr_text(image)
    findings = []

    if palette_result.get("status") == "review_required":
        findings.append({
            "category": "colour_compliance", "severity": "warning",
            "title": "Detected colours outside the approved palette",
            "details": palette_result["message"], "evidence": palette_result["off_palette"],
            "recommendation": "Confirm whether the flagged colours are authorised campaign or accessibility colours, otherwise replace them with the approved palette.",
        })
    elif not palette_result.get("configured"):
        findings.append({
            "category": "colour_compliance", "severity": "info",
            "title": "Brand palette not configured",
            "details": "Colour compliance could not be evaluated because no approved palette has been saved.",
            "evidence": [], "recommendation": "Add the official HEX colours in Visual Brand Compliance settings.",
        })

    if logo_reference_path and Path(logo_reference_path).is_file():
        try:
            reference = Image.open(logo_reference_path).convert("RGB")
            score = logo_candidate_score(image, reference)
            state = "candidate_match" if score >= 0.78 else "not_detected"
            findings.append({
                "category": "logo_compliance", "severity": "info" if state == "candidate_match" else "warning",
                "title": "Logo similarity candidate detected" if state == "candidate_match" else "Approved logo not confidently detected",
                "details": f"Best perceptual-hash similarity score: {score:.3f}. This is a visual screening signal, not proof of logo identity.",
                "similarity": score, "evidence": [],
                "recommendation": "Human reviewer should confirm logo identity, placement, proportions and clear space." if state == "candidate_match" else "Confirm that the creative uses the current approved logo and that it is visible at sufficient size.",
            })
        except Exception:
            findings.append({"category":"logo_compliance","severity":"warning","title":"Logo reference could not be analysed","details":"The saved reference asset could not be opened.","evidence":[],"recommendation":"Upload a valid PNG, JPEG or WebP logo reference again."})
    else:
        findings.append({
            "category": "logo_compliance", "severity": "info", "title": "No approved logo reference configured",
            "details": "Logo similarity screening was skipped because an approved reference logo has not been uploaded.",
            "evidence": [], "recommendation": "Upload the official logo before using logo similarity screening.",
        })

    if ocr_text:
        for term in forbidden_terms:
            if term and term.casefold() in ocr_text.casefold():
                findings.append({
                    "category": "image_text_terminology", "severity": "warning",
                    "title": f"Restricted terminology detected in image text: {term}",
                    "details": "OCR detected a phrase from the restricted terminology list. OCR can misread text, so verify the extracted wording against the original image.",
                    "evidence": [{"term": term}], "recommendation": "Replace the restricted phrase with approved wording after visually confirming the text.",
                })

    return {
        "filename": Path(filename).name[:180], "width": image.width, "height": image.height,
        "sha256": sha256(raw), "dominant_colors": colors, "palette_check": palette_result,
        "ocr_text": ocr_text, "ocr_message": ocr_message, "findings": findings,
        "disclaimer": "Automated visual screening is advisory. Perceptual similarity and RGB palette checks can produce false positives and false negatives. Human verification is required.",
    }
