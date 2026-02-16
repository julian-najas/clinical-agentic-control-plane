"""Worker — processes queued actions with compliance rails."""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    import redis

    from cacp.consent import ConsentStoreProtocol
    from cacp.storage.event_store import EventStoreProtocol

from cacp.queue.enqueue import QUEUE_NAME

__all__ = ["Worker", "ActionAdapter", "NoopAdapter"]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Adapter protocol
# ---------------------------------------------------------------------------


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
        return {
            "adapter": "noop",
            "action_type": action_type,
            "status": "executed",
        }


# ---------------------------------------------------------------------------
# Compliance rails
# ---------------------------------------------------------------------------


def _check_consent(
    action: dict[str, Any],
    consent_store: ConsentStoreProtocol | None,
) -> str | None:
    """Return blocking reason or None if consent OK."""
    if consent_store is None:
        return None  # no store → skip check
    patient_id = action.get("patient_id", "")
    channel = action.get("channel", "sms")
    if not patient_id:
        return None  # cannot check → allow (fail-open for missing id)
    if not consent_store.has_consent(patient_id, channel):
        return "no_consent"
    return None


def _check_quiet_hours(
    quiet_start: int,
    quiet_end: int,
) -> str | None:
    """Return blocking reason if current hour is inside quiet window."""
    hour = datetime.now(UTC).hour
    if quiet_start <= quiet_end:
        # e.g. 02:00-06:00
        if quiet_start <= hour < quiet_end:
            return "quiet_hours"
    else:
        # e.g. 22:00-08:00 (wraps midnight)
        if hour >= quiet_start or hour < quiet_end:
            return "quiet_hours"
    return None


def _check_rate_limit(
    action: dict[str, Any],
    redis_client: redis.Redis,  # type: ignore[type-arg]
    limit: int,
    window: int,
) -> str | None:
    """Sliding-window rate limit per patient+channel. Returns reason or None."""
    patient_id = action.get("patient_id", "")
    channel = action.get("channel", "sms")
    if not patient_id or limit <= 0:
        return None
    key = f"cacp:rate:{patient_id}:{channel}"
    now = time.time()
    pipe = redis_client.pipeline()
    pipe.zremrangebyscore(key, 0, now - window)
    pipe.zcard(key)
    pipe.zadd(key, {str(now): now})
    pipe.expire(key, window)
    results = pipe.execute()  # type: ignore[union-attr]
    current_count: int = results[1]  # type: ignore[assignment]
    if current_count >= limit:
        return "rate_limited"
    return None


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------


class Worker:
    """Blocking worker that dequeues and executes actions."""

    def __init__(
        self,
        redis_client: redis.Redis,  # type: ignore[type-arg]
        adapters: dict[str, ActionAdapter] | None = None,
        event_store: EventStoreProtocol | None = None,
        consent_store: ConsentStoreProtocol | None = None,
        quiet_hours_start: int = 22,
        quiet_hours_end: int = 8,
        sms_rate_limit: int = 3,
        sms_rate_window: int = 86400,
    ) -> None:
        self._redis = redis_client
        self._adapters: dict[str, ActionAdapter] = adapters or {
            "execute_plan": NoopAdapter(),
        }
        self._events = event_store
        self._consent = consent_store
        self._quiet_start = quiet_hours_start
        self._quiet_end = quiet_hours_end
        self._rate_limit = sms_rate_limit
        self._rate_window = sms_rate_window

    # -- event helper -------------------------------------------------------

    def _emit(
        self,
        aggregate_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        if self._events is None:
            return
        try:
            self._events.append(
                aggregate_id=aggregate_id,
                event_type=event_type,
                payload=payload,
            )
        except Exception:
            logger.warning(
                "Event store append failed for %s",
                event_type,
                exc_info=True,
            )

    # -- rail pipeline ------------------------------------------------------

    def _apply_rails(
        self,
        action: dict[str, Any],
    ) -> str | None:
        """Run compliance rails. Return reason string if blocked, else None."""
        # 1. Consent
        reason = _check_consent(action, self._consent)
        if reason:
            return reason

        # 2. Quiet hours
        reason = _check_quiet_hours(self._quiet_start, self._quiet_end)
        if reason:
            return reason

        # 3. Rate limit (needs Redis)
        reason = _check_rate_limit(
            action,
            self._redis,
            self._rate_limit,
            self._rate_window,
        )
        if reason:
            return reason

        return None

    # -- execute ------------------------------------------------------------

    def _execute(self, action: dict[str, Any]) -> dict[str, Any] | None:
        """Execute a single action via adapter, emit audit event."""
        action_type = action.get("action_type", "unknown")
        aggregate_id = action.get("appointment_id") or action.get("pr_number", "unknown")
        aggregate_id = str(aggregate_id)

        adapter = self._adapters.get(action_type)
        if not adapter:
            logger.warning("No adapter for action type: %s", action_type)
            self._emit(
                aggregate_id,
                "action_failed",
                {**action, "reason": "no_adapter"},
            )
            return None

        # -- Compliance rails --
        block_reason = self._apply_rails(action)
        if block_reason:
            logger.info(
                "Action blocked (%s): %s patient=%s",
                block_reason,
                action_type,
                action.get("patient_id", "?"),
            )
            self._emit(
                aggregate_id,
                "action_blocked",
                {**action, "reason": block_reason},
            )
            return {"blocked": True, "reason": block_reason}

        # -- Execute adapter --
        try:
            result = adapter.execute(action)
            self._emit(
                aggregate_id,
                "action_executed",
                {**action, **result},
            )
            logger.info("Executed action: %s", action_type)
            return result
        except Exception:
            logger.exception("Adapter failed for %s", action_type)
            self._emit(
                aggregate_id,
                "action_failed",
                {**action, "reason": "adapter_error"},
            )
            return None

    # -- public loop --------------------------------------------------------

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
            action: dict[str, Any] = json.loads(
                raw,  # type: ignore[arg-type]
            )
            self._execute(action)
