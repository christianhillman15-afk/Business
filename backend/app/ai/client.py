"""Thin wrapper around the Anthropic SDK.

If no API key is configured the wrapper reports ``enabled == False`` and callers
fall back to deterministic offline logic, so the whole app runs without a key.
"""
from __future__ import annotations

import json
import logging

from ..config import settings

logger = logging.getLogger("leadpilot.ai")

try:  # pragma: no cover - import guard
    import anthropic
except Exception:  # noqa: BLE001
    anthropic = None  # type: ignore[assignment]


class AIClient:
    def __init__(self) -> None:
        self._client = None
        if settings.ai_enabled and anthropic is not None:
            try:
                self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Anthropic client init failed, using fallback: %s", exc)
                self._client = None

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def complete_text(
        self, *, system: str, prompt: str, model: str, max_tokens: int = 1024
    ) -> str | None:
        """Return plain text from Claude, or None if the AI layer is disabled."""
        if not self.enabled:
            return None
        try:
            msg = self._client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            return "".join(b.text for b in msg.content if b.type == "text").strip()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Claude completion failed, using fallback: %s", exc)
            return None

    def complete_json(
        self, *, system: str, prompt: str, schema: dict, model: str, max_tokens: int = 1024
    ) -> dict | None:
        """Return a JSON object constrained to ``schema``, or None if disabled."""
        if not self.enabled:
            return None
        try:
            msg = self._client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                output_config={"format": {"type": "json_schema", "schema": schema}},
            )
            text = next((b.text for b in msg.content if b.type == "text"), "")
            return json.loads(text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Claude JSON completion failed, using fallback: %s", exc)
            return None


_ai_client: AIClient | None = None


def get_ai() -> AIClient:
    global _ai_client
    if _ai_client is None:
        _ai_client = AIClient()
    return _ai_client
