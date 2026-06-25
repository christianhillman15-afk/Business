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
    access_token_expire_minutes: int = 10080  # 7 days
    cors_origins: str = "http://localhost:3000"

    # Billing
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def ai_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
