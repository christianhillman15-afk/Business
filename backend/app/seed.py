"""Seed the database with plans context, a demo provider, and an admin.

Run with:  python -m app.seed
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from .database import SessionLocal, init_db
from .models import (
    AccountProvider,
    ClientPricingProfile,
    ConnectedAccount,
    ConnectionHealth,
    Subscription,
    SubscriptionStatus,
    User,
    UserRole,
)
from .security import hash_password


def seed() -> None:
    init_db()
    db = SessionLocal()
    try:
        if db.execute(select(User).limit(1)).first():
            print("Database already seeded.")
            return

        admin = User(
            email="admin@leadpilot.io",
            password_hash=hash_password("admin1234"),
            role=UserRole.admin,
            business_name="LeadPilot HQ",
        )
        admin.subscription = Subscription(
            plan_code="scale", status=SubscriptionStatus.active
        )
        admin.pricing_profile = ClientPricingProfile()
        db.add(admin)

        provider = User(
            email="demo@leadpilot.io",
            password_hash=hash_password("demo1234"),
            role=UserRole.provider,
            business_name="Rivertown Plumbing Co.",
            timezone="America/New_York",
        )
        provider.subscription = Subscription(
            plan_code="growth",
            status=SubscriptionStatus.active,
            trial_end=datetime.now(timezone.utc) + timedelta(days=7),
        )
        provider.pricing_profile = ClientPricingProfile(
            trade="plumbing",
            service_categories="leak repair, water heaters, drain cleaning, "
            "fixture installation, emergency plumbing",
            price_list="Service call $89; drain cleaning from $150; water heater "
            "install from $1,200",
            phone="(555) 014-7788",
            target_neighborhoods="Rivertown, Maple Heights",
        )
        provider.connected_accounts = [
            ConnectedAccount(
                provider=AccountProvider.facebook,
                display_name="Rivertown Plumbing",
                encrypted_session="stub-session:demo",
                health=ConnectionHealth.healthy,
            ),
            ConnectedAccount(
                provider=AccountProvider.nextdoor,
                display_name="Rivertown Plumbing (Nextdoor)",
                encrypted_session="stub-session:demo",
                health=ConnectionHealth.healthy,
            ),
        ]
        db.add(provider)
        db.commit()

        print("Seeded:")
        print("  admin@leadpilot.io / admin1234  (admin)")
        print("  demo@leadpilot.io  / demo1234   (provider: Rivertown Plumbing)")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
