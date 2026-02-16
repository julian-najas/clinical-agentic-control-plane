"""HMAC-SHA256 signing and verification."""

from __future__ import annotations

import hashlib
import hmac as hmac_mod
from typing import Any

from cacp.signing.canonical import canonicalise

__all__ = ["sign_payload", "verify_signature"]

_EXCLUDE = {"hmac_signature"}


def sign_payload(payload: dict[str, Any], secret: str) -> str:
    """Sign a payload with HMAC-SHA256 and return the hex digest."""
    canonical = canonicalise(payload, exclude_keys=_EXCLUDE)
    return hmac_mod.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()


def verify_signature(payload: dict[str, Any], secret: str) -> bool:
    """Verify that a payload's hmac_signature matches the expected value."""
    expected = payload.get("hmac_signature", "")
    if not expected:
        return False
    computed = sign_payload(payload, secret)
    return hmac_mod.compare_digest(computed, expected)
