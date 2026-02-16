"""Enqueue actions for worker execution."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import redis

__all__ = ["enqueue_action"]

QUEUE_NAME = "cacp:actions"


def enqueue_action(client: redis.Redis[bytes], action: dict[str, Any]) -> int:
    """Push an action onto the Redis queue. Returns queue length."""
    return client.rpush(QUEUE_NAME, json.dumps(action))
