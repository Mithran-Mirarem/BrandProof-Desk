"""Agentverse Agent Chat Protocol adapter for BrandProof Desk.

This exposes ACP over FastAPI at POST /chat and a GET /status health check.
The regular BrandProof REST API remains unchanged.
"""
from __future__ import annotations

import os
from typing import cast

from fastapi import APIRouter, HTTPException
from uagents_core.envelope import Envelope

from . import db
from .review import run_review

router = APIRouter(tags=["Agentverse ACP"])


def _identity():
    """Build a stable identity from the private seed phrase in backend/.env."""
    seed = os.getenv("AGENT_SEED_PHRASE", "").strip()
    if not seed:
        raise HTTPException(
            status_code=503,
            detail="Agentverse is not configured. Set AGENT_SEED_PHRASE in backend/.env.",
        )
    from uagents_core.identity import Identity

    return Identity.from_seed(seed, 0)


@router.get("/status")
def agentverse_status():
    """Public health-check endpoint used during Agentverse onboarding."""
    configured = bool(os.getenv("AGENT_SEED_PHRASE", "").strip())
    return {
        "status": "ok" if configured else "needs_configuration",
        "agent": "BrandProof Desk",
        "protocol": "ACP",
        "chat_endpoint": "/chat",
        "identity_configured": configured,
    }


@router.post("/chat")
async def agentverse_chat(env: Envelope):
    """Receive an ACP ChatMessage, review it with BrandProof, and reply."""
    # Imports are local so the regular REST app can still start if the optional
    # Agentverse dependency has not yet been installed during local setup.
    try:
        from uagents_core.contrib.protocols.chat import ChatMessage, TextContent
        from uagents_core.utils.messages import parse_envelope, send_message_to_agent
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail="Install uagents-core to enable Agentverse ACP integration.",
        ) from exc

    if not isinstance(env, Envelope):
        # FastAPI normally validates this through the endpoint annotation below;
        # this branch is retained as a defensive check for direct invocation.
        raise HTTPException(status_code=400, detail="Invalid ACP envelope.")

    try:
        incoming = cast(ChatMessage, parse_envelope(env, ChatMessage))
        content = (incoming.text() or "").strip()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Could not parse ACP chat message.") from exc

    if len(content) < 10:
        raise HTTPException(status_code=400, detail="Please send at least 10 characters of content to review.")
    if len(content) > 30000:
        raise HTTPException(status_code=413, detail="Message is too long. Maximum length is 30,000 characters.")

    try:
        review = run_review(content, "Agentverse / ASI:One", "Brand governance review", db.get_brand())
        db.add_review(review)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Brand review failed. Please retry.") from exc

    findings = review.get("findings", [])
    lines = [
        "BrandProof Desk completed a brand-governance review.",
        f"Review ID: {review.get('id', 'unknown')}",
        f"Mode: {review.get('agent_mode', 'rules_fallback')}",
        f"Findings: {len(findings)}",
    ]
    for index, finding in enumerate(findings[:5], start=1):
        lines.append(
            f"{index}. [{finding.get('severity', 'review').upper()}] "
            f"{finding.get('category', 'brand issue')}: "
            f"{finding.get('explanation', 'Review required.')[:350]}"
        )
        if finding.get("evidence_ids"):
            lines.append("   Evidence: " + ", ".join(finding["evidence_ids"][:5]))
        if finding.get("suggestion"):
            lines.append("   Suggested action: " + finding["suggestion"][:250])
    if len(findings) > 5:
        lines.append(f"Additional findings: {len(findings) - 5}. Open the BrandProof Desk dashboard for the complete report.")
    lines.append("Human review is required. This agent does not publish content or approve it automatically.")
    reply = "\n".join(lines)

    try:
        send_message_to_agent(
            destination=env.sender,
            msg=ChatMessage([TextContent(reply)]),
            sender=_identity(),
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Could not send the ACP response to the requesting agent.") from exc

    return {"status": "accepted", "review_id": review.get("id")}
