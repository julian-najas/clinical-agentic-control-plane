"""Canonical JSON serialisation for HMAC signing."""

from __future__ import annotations

import json
from typing import Any

__all__ = ["canonicalise"]


def canonicalise(payload: dict[str, Any], exclude_keys: set[str] | None = None) -> str:
    """Produce canonical JSON: sorted keys, no whitespace, excluded keys removed.

    Args:
        payload: The dictionary to serialise.
        exclude_keys: Keys to remove before serialisation (e.g. {"hmac_signature"}).

    Returns:
        Deterministic JSON string suitable for HMAC signing.
    """
    if exclude_keys:
        payload = {k: v for k, v in payload.items() if k not in exclude_keys}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
