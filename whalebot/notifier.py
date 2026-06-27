"""Pluggable alert delivery: console, JSONL file, webhook, Telegram."""

from __future__ import annotations

import json
import logging
import os
import time

import requests

from .config import NotificationsConfig
from .models import Signal

log = logging.getLogger("whalebot.notifier")


class Notifier:
    def __init__(self, cfg: NotificationsConfig) -> None:
        self.cfg = cfg

    def send(self, sig: Signal) -> None:
        """Best-effort fan-out to every enabled channel."""
        if self.cfg.console:
            self._console(sig)
        if self.cfg.file.enabled:
            self._file(sig)
        if self.cfg.webhook.enabled:
            self._webhook(sig)
        if self.cfg.telegram.enabled:
            self._telegram(sig)

    def info(self, message: str) -> None:
        """Send a plain operational message (e.g. paper-account summaries)."""
        if self.cfg.console:
            log.info(message)
        if self.cfg.webhook.enabled:
            self._post_webhook(message)
        if self.cfg.telegram.enabled:
            self._post_telegram(message)

    # -- channels ----------------------------------------------------------
    def _console(self, sig: Signal) -> None:
        log.warning("🐋 %s", sig.summary())

    def _file(self, sig: Signal) -> None:
        row = sig.to_dict()
        row["ts"] = time.time()
        row["iso"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(row["ts"]))
        try:
            with open(self.cfg.file.path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
        except Exception as exc:  # noqa: BLE001
            log.warning("could not write alert to %s: %s", self.cfg.file.path, exc)

    def _webhook(self, sig: Signal) -> None:
        self._post_webhook(f"🐋 {sig.summary()}")

    def _post_webhook(self, text: str) -> None:
        url = os.environ.get(self.cfg.webhook.url_env, "")
        if not url:
            log.debug("webhook enabled but %s is unset", self.cfg.webhook.url_env)
            return
        try:
            # `content` works for Discord; `text` for Slack — send both keys.
            requests.post(url, json={"content": text, "text": text}, timeout=8)
        except Exception as exc:  # noqa: BLE001
            log.warning("webhook post failed: %s", exc)

    def _telegram(self, sig: Signal) -> None:
        self._post_telegram(f"🐋 {sig.summary()}")

    def _post_telegram(self, text: str) -> None:
        token = os.environ.get(self.cfg.telegram.bot_token_env, "")
        chat_id = self.cfg.telegram.chat_id
        if not token or not chat_id:
            log.debug("telegram enabled but token/chat_id missing")
            return
        try:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text},
                timeout=8,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("telegram post failed: %s", exc)
