"""Worker — processes queued actions after PR merge."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    import redis

    from cacp.storage.event_store import EventStoreProtocol

from cacp.queue.enqueue import QUEUE_NAME

__all__ = ["Worker", "ActionAdapter", "NoopAdapter"]

logger = logging.getLogger(__name__)


class ActionAdapter(Protocol):
    """Interface for action execution adapters."""

    def execute(self, action: dict[str, Any]) -> dict[str, Any]:
        """Execute an action, return result metadata."""
        ...


class NoopAdapter:
    """Stub adapter — logs execution without side effects."""

    def execute(self, action: dict[str, Any]) -> dict[str, Any]:
        action_type = action.get("action_type", "unknown")
        logger.info(
            "NOOP executing: %s (appointment=%s)",
            action_type,
            action.get("appointment_id"),
        )
        return {"adapter": "noop", "action_type": action_type, "status": "executed"}


class Worker:
    """Blocking worker that dequeues and executes actions."""

    def __init__(
        self,
        redis_client: redis.Redis,  # type: ignore[type-arg]
        adapters: dict[str, ActionAdapter] | None = None,
        event_store: EventStoreProtocol | None = None,
    ) -> None:
        self._redis = redis_client
        self._adapters: dict[str, ActionAdapter] = adapters or {"execute_plan": NoopAdapter()}
        self._events = event_store

    def _emit(self, aggregate_id: str, event_type: str, payload: dict[str, Any]) -> None:
        if self._events is None:
            return
        try:
            self._events.append(
                aggregate_id=aggregate_id,
                event_type=event_type,
                payload=payload,
            )
        except Exception:
            logger.warning("Event store append failed for %s", event_type, exc_info=True)

    def _execute(self, action: dict[str, Any]) -> dict[str, Any] | None:
        """Execute a single action via adapter, emit audit event."""
        action_type = action.get("action_type", "unknown")
        aggregate_id = action.get("appointment_id") or action.get("pr_number", "unknown")
        aggregate_id = str(aggregate_id)

        adapter = self._adapters.get(action_type)
        if not adapter:
            logger.warning("No adapter for action type: %s", action_type)
            self._emit(aggregate_id, "action_failed", {**action, "reason": "no_adapter"})
            return None

        try:
            result = adapter.execute(action)
            self._emit(aggregate_id, "action_executed", {**action, **result})
            logger.info("Executed action: %s", action_type)
            return result
        except Exception:
            logger.exception("Adapter failed for %s", action_type)
            self._emit(aggregate_id, "action_failed", {**action, "reason": "adapter_error"})
            return None

    def run_once(self) -> dict[str, Any] | None:
        """Dequeue and process one action. Returns the action or None."""
        raw = self._redis.lpop(QUEUE_NAME)
        if raw is None:
            return None

        action: dict[str, Any] = json.loads(raw)  # type: ignore[arg-type]
        self._execute(action)
        return action

    def run_loop(self, timeout: float = 5.0) -> None:
        """Blocking loop — dequeue actions until stopped."""
        logger.info("Worker started, listening on queue: %s", QUEUE_NAME)
        while True:
            result = self._redis.blpop([QUEUE_NAME], timeout=int(timeout))
            if result is None:
                continue
            _, raw = result  # type: ignore[misc]
            action: dict[str, Any] = json.loads(raw)  # type: ignore[arg-type]
            self._execute(action)
