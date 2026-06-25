"""Background / scheduled jobs.

Run on demand:
    python -m app.tasks discover-all
    python -m app.tasks recruit

Or enable the in-process scheduler with LEADPILOT_SCHEDULER_ENABLED=true, which
runs ``discover_all`` every LEADPILOT_SCHEDULER_INTERVAL_MINUTES.
"""
from __future__ import annotations

import logging
import sys

from sqlalchemy import select

from .database import SessionLocal
from .models import SubscriptionStatus, User, UserRole
from .services import run_discovery, run_recruiting

logger = logging.getLogger("leadpilot.tasks")

_ACTIVE_STATUSES = (SubscriptionStatus.active, SubscriptionStatus.trialing)


def discover_all() -> dict:
    """Run a discovery sweep for every active provider with automation on."""
    db = SessionLocal()
    try:
        providers = (
            db.execute(
                select(User).where(
                    User.role == UserRole.provider,
                    User.automation_enabled.is_(True),
                )
            )
            .scalars()
            .all()
        )
        leads = 0
        scanned = 0
        for p in providers:
            if p.subscription and p.subscription.status in _ACTIVE_STATUSES:
                scanned += 1
                leads += len(run_discovery(db, p))
        result = {"providers_scanned": scanned, "leads_created": leads}
        logger.info("discover_all: %s", result)
        return result
    finally:
        db.close()


def recruit() -> dict:
    db = SessionLocal()
    try:
        created = run_recruiting(db)
        result = {"recruits_created": len(created)}
        logger.info("recruit: %s", result)
        return result
    finally:
        db.close()


def start_scheduler() -> object | None:
    """Start the APScheduler background scheduler if enabled. Returns it."""
    from .config import settings

    if not settings.leadpilot_scheduler_enabled:
        return None
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except Exception as exc:  # noqa: BLE001
        logger.warning("APScheduler unavailable, scheduler disabled: %s", exc)
        return None

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        discover_all,
        "interval",
        minutes=settings.leadpilot_scheduler_interval_minutes,
        id="discover_all",
    )
    scheduler.start()
    logger.info(
        "Scheduler started: discover_all every %s min",
        settings.leadpilot_scheduler_interval_minutes,
    )
    return scheduler


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "discover-all"
    if cmd == "discover-all":
        print(discover_all())
    elif cmd == "recruit":
        print(recruit())
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: python -m app.tasks [discover-all|recruit]")
        sys.exit(1)
