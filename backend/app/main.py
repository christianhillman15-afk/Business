"""LeadPilot API entrypoint."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import init_db
from .routers import (
    accounts,
    admin,
    auth,
    leads,
    profile,
    responses,
    subscription,
    support,
)

app = FastAPI(
    title="LeadPilot API",
    version="0.1.0",
    description="AI-powered lead discovery and outreach for local service businesses.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "ai_enabled": settings.ai_enabled}


for r in (
    auth.router,
    profile.router,
    accounts.router,
    leads.router,
    responses.router,
    subscription.router,
    support.router,
    admin.router,
):
    app.include_router(r)
