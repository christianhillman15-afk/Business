"""AES-256-GCM encryption for connected-account sessions / credentials.

Connected social sessions are sensitive (the spec requires AES-256 at rest).
The 256-bit key is derived from ``ENCRYPTION_KEY`` (or ``SECRET_KEY`` as a dev
fallback) via SHA-256. Ciphertext is stored as ``v1:<nonce_hex>:<ct_hex>``.

If the ``cryptography`` package is unavailable, we fall back to a clearly-marked
non-encrypted marker so the app still runs in minimal dev setups — never rely on
that path in production (a startup warning is logged).
"""
from __future__ import annotations

import hashlib
import logging
import os

from .config import settings

logger = logging.getLogger("leadpilot.crypto")

try:  # pragma: no cover - import guard
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    _AVAILABLE = True
except Exception:  # noqa: BLE001
    AESGCM = None  # type: ignore[assignment]
    _AVAILABLE = False
    logger.warning(
        "cryptography not installed — connected sessions will NOT be encrypted. "
        "Do not use this configuration in production."
    )

_PREFIX = "v1"
_PLAINTEXT_PREFIX = "plain"


def _key() -> bytes:
    secret = (settings.encryption_key or settings.secret_key).encode()
    return hashlib.sha256(secret).digest()  # 32 bytes -> AES-256


def encrypt(plaintext: str | None) -> str | None:
    if plaintext is None:
        return None
    if not _AVAILABLE:
        return f"{_PLAINTEXT_PREFIX}:{plaintext}"
    nonce = os.urandom(12)
    ct = AESGCM(_key()).encrypt(nonce, plaintext.encode(), None)
    return f"{_PREFIX}:{nonce.hex()}:{ct.hex()}"


def decrypt(token: str | None) -> str | None:
    if token is None:
        return None
    if token.startswith(f"{_PLAINTEXT_PREFIX}:"):
        return token.split(":", 1)[1]
    if not token.startswith(f"{_PREFIX}:"):
        # Legacy / opaque stub markers — nothing to decrypt.
        return None
    try:
        _, nonce_hex, ct_hex = token.split(":", 2)
        pt = AESGCM(_key()).decrypt(
            bytes.fromhex(nonce_hex), bytes.fromhex(ct_hex), None
        )
        return pt.decode()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to decrypt session token: %s", exc)
        return None
