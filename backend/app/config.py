"""Application configuration, loaded from environment / .env."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), env_prefix="", extra="ignore"
    )

    # AI
    anthropic_api_key: str | None = None
    leadpilot_ai_model: str = "claude-opus-4-8"
    leadpilot_ai_classifier_model: str = "claude-haiku-4-5"

    # Backend
    database_url: str = "sqlite:///./leadpilot.db"
    secret_key: str = "dev-insecure-change-me"
    encryption_key: str | None = None  # AES-256 key material for sessions at rest
    access_token_expire_minutes: int = 10080  # 7 days
    cors_origins: str = "http://localhost:3000"
    frontend_base_url: str = "http://localhost:3000"

    # Connectors / safety
    # When False, real connectors never publish (drafts still flow). Keeps
    # connected accounts safe until you explicitly opt in. See docs/COMPLIANCE.md.
    leadpilot_live_connectors: bool = False
    # Comma-separated Meta Group/Page IDs the connected account can read.
    meta_group_ids: str | None = None
    # Background discovery scheduler (APScheduler). Off by default.
    leadpilot_scheduler_enabled: bool = False
    leadpilot_scheduler_interval_minutes: int = 30

    # Billing
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    # Optional map of plan_code -> Stripe price id (JSON or "code:price,code:price").
    stripe_prices: str | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def meta_group_id_list(self) -> list[str]:
        return [g.strip() for g in (self.meta_group_ids or "").split(",") if g.strip()]

    @property
    def stripe_price_map(self) -> dict[str, str]:
        raw = self.stripe_prices
        if not raw:
            return {}
        out: dict[str, str] = {}
        for pair in raw.split(","):
            if ":" in pair:
                code, price = pair.split(":", 1)
                out[code.strip()] = price.strip()
        return out

    @property
    def ai_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
