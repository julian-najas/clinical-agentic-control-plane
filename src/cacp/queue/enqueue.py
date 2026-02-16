"""Enqueue actions for worker execution."""

from __future__ import annotations

import json
from typing import Any

import redis

__all__ = ["enqueue_action"]

QUEUE_NAME = "cacp:actions"


def enqueue_action(client: redis.Redis, action: dict[str, Any]) -> int:  # type: ignore[type-arg]
    """Push an action onto the Redis queue. Returns queue length."""
    return client.rpush(QUEUE_NAME, json.dumps(action))  # type: ignore[return-value]
