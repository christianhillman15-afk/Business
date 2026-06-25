"""Password hashing and JWT helpers.

Hashing uses Argon2id (the algorithm the spec calls for) when ``argon2-cffi`` is
available, and transparently falls back to PBKDF2-HMAC-SHA256 from the standard
library otherwise. ``verify_password`` accepts either format, so existing
PBKDF2 hashes keep working after an Argon2 upgrade.
"""
from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt

from .config import settings

try:  # pragma: no cover - import guard
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError

    _ph: PasswordHasher | None = PasswordHasher()
except Exception:  # noqa: BLE001
    _ph = None
    VerifyMismatchError = Exception  # type: ignore[assignment,misc]

_PBKDF2_ROUNDS = 240_000
_ALGO = "HS256"


def hash_password(password: str) -> str:
    if _ph is not None:
        return _ph.hash(password)  # "$argon2id$..."
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    if stored.startswith("$argon2"):
        if _ph is None:
            return False
        try:
            return _ph.verify(stored, password)
        except VerifyMismatchError:
            return False
        except Exception:  # noqa: BLE001
            return False
    try:
        algo, rounds, salt_hex, digest_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        expected = bytes.fromhex(digest_hex)
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(rounds)
        )
        return hmac.compare_digest(candidate, expected)
    except (ValueError, AttributeError):
        return False


def create_access_token(subject: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=_ALGO)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[_ALGO])
    except jwt.PyJWTError:
        return None
