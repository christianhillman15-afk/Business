"""LeadPilot API entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import init_db
from .routers import (
    account,
    accounts,
    admin,
    auth,
    broadcast,
    leads,
    notifications,
    oauth,
    profile,
    responses,
    sms,
    subscription,
    support,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    from .tasks import start_scheduler

    app.state.scheduler = start_scheduler()
    yield
    scheduler = getattr(app.state, "scheduler", None)
    if scheduler is not None:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="LeadPilot API",
    version="0.1.0",
    description="AI-powered lead discovery and outreach for local service businesses.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "ai_enabled": settings.ai_enabled}


for r in (
    auth.router,
    account.router,
    profile.router,
    accounts.router,
    leads.router,
    responses.router,
    broadcast.router,
    subscription.router,
    support.router,
    sms.router,
    notifications.router,
    oauth.router,
    admin.router,
):
    app.include_router(r)
