"""Dedicated public surface for Agentverse ACP.

Run this on port 8001 and tunnel only this process. Keep the main BrandProof
REST API on port 8000 private during the Agentverse onboarding test.
"""
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from fastapi import FastAPI
from app import db
from app.agentverse import router as agentverse_router

db.init_db()
app = FastAPI(
    title="BrandProof Desk Agentverse ACP",
    version="0.1.0",
    description="Agent Chat Protocol endpoint for BrandProof Desk",
)
app.include_router(agentverse_router)

@app.get("/")
def root():
    return {"service": "BrandProof Desk Agentverse ACP", "status": "ok", "chat_endpoint": "/chat", "health_endpoint": "/status"}
