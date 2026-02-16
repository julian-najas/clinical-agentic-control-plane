"""No-op adapter for testing — logs actions without executing them."""

from __future__ import annotations

import logging
from typing import Any

__all__ = ["NoopAdapter"]

logger = logging.getLogger(__name__)


class NoopAdapter:
    """Adapter that logs actions without side effects. For testing only."""

    def execute(self, action: dict[str, Any]) -> None:
        logger.info("[NOOP] Would execute: %s", action)
