"""Worker — processes queued actions after PR merge."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import redis

from cacp.queue.enqueue import QUEUE_NAME

__all__ = ["Worker"]

logger = logging.getLogger(__name__)


class Worker:
    """Blocking worker that dequeues and executes actions."""

    def __init__(
        self,
        redis_client: redis.Redis,  # type: ignore[type-arg]
        adapters: dict[str, Any] | None = None,
    ) -> None:
        self._redis = redis_client
        self._adapters = adapters or {}

    def run_once(self) -> dict[str, Any] | None:
        """Dequeue and process one action. Returns the action or None."""
        raw = self._redis.lpop(QUEUE_NAME)
        if raw is None:
            return None

        action = json.loads(raw)  # type: ignore[arg-type]
        action_type = action.get("action_type", "unknown")

        adapter = self._adapters.get(action_type)
        if adapter:
            adapter.execute(action)
            logger.info("Executed action: %s", action_type)
        else:
            logger.warning("No adapter for action type: %s", action_type)

        return action  # type: ignore[no-any-return]

    def run_loop(self, timeout: float = 5.0) -> None:
        """Blocking loop — dequeue actions until stopped."""
        logger.info("Worker started, listening on queue: %s", QUEUE_NAME)
        while True:
            result = self._redis.blpop(QUEUE_NAME, timeout=int(timeout))
            if result is None:
                continue
            _, raw = result
            action = json.loads(raw)  # type: ignore[arg-type]
            action_type = action.get("action_type", "unknown")
            adapter = self._adapters.get(action_type)
            if adapter:
                adapter.execute(action)
