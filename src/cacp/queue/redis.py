"""Redis connection management."""

from __future__ import annotations

import redis

__all__ = ["get_redis_client"]


def get_redis_client(url: str = "redis://localhost:6379/0") -> redis.Redis:  # type: ignore[type-arg]
    """Create a Redis client."""
    return redis.Redis.from_url(url, decode_responses=True)
