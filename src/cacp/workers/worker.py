"""Worker — processes queued actions with compliance rails, retry, DLQ."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    import redis

    from cacp.consent import ConsentStoreProtocol
    from cacp.storage.event_store import EventStoreProtocol

from cacp.queue.enqueue import QUEUE_NAME

__all__ = ["Worker", "ActionAdapter", "NoopAdapter"]

logger = logging.getLogger(__name__)

# Redis keys for retry and dead-letter queues
RETRY_ZSET = "cacp:retry"
DLQ_KEY = "cacp:dlq"


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
        return "no_patient_id"  # fail-closed: cannot verify consent without patient_id
    if not consent_store.has_consent(patient_id, channel):
        return "no_consent"
    return None


def _check_quiet_hours(
    quiet_start: int,
    quiet_end: int,
    tz_name: str,
) -> str | None:
    """Return blocking reason if current hour is inside quiet window.

    Evaluates in clinic local time via *tz_name* (e.g. Europe/Madrid).
    """
    hour = datetime.now(ZoneInfo(tz_name)).hour
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
    """Sliding-window rate limit per patient+channel."""
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


def _check_dedup(
    action: dict[str, Any],
    redis_client: redis.Redis,  # type: ignore[type-arg]
    ttl: int,
) -> str | None:
    """Atomic dedup per appointment_id + channel. Returns reason or None."""
    appointment_id = action.get("appointment_id", "")
    channel = action.get("channel", "sms")
    if not appointment_id:
        return None
    dedup_key = f"cacp:sent:{appointment_id}:{channel}"
    acquired = redis_client.set(
        dedup_key,
        "1",
        nx=True,
        ex=ttl,
    )  # type: ignore[union-attr]
    if not acquired:
        return "duplicate_action"
    return None


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------


class Worker:
    """Blocking worker with compliance rails, retry + DLQ."""

    def __init__(
        self,
        redis_client: redis.Redis,  # type: ignore[type-arg]
        adapters: dict[str, ActionAdapter] | None = None,
        event_store: EventStoreProtocol | None = None,
        consent_store: ConsentStoreProtocol | None = None,
        quiet_hours_start: int = 22,
        quiet_hours_end: int = 8,
        timezone: str = "Europe/Madrid",
        sms_rate_limit: int = 3,
        sms_rate_window: int = 86400,
        dedup_ttl: int = 86400,
        max_retries: int = 3,
        retry_backoff: list[int] | None = None,
    ) -> None:
        self._redis = redis_client
        self._adapters: dict[str, ActionAdapter] = adapters or {
            "execute_plan": NoopAdapter(),
        }
        self._events = event_store
        self._consent = consent_store
        self._quiet_start = quiet_hours_start
        self._quiet_end = quiet_hours_end
        self._tz = timezone
        self._rate_limit = sms_rate_limit
        self._rate_window = sms_rate_window
        self._dedup_ttl = dedup_ttl
        self._max_retries = max_retries
        self._backoff = retry_backoff or [60, 300, 900]

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
        """Run compliance rails. Return reason string if blocked."""
        # 1. Consent
        reason = _check_consent(action, self._consent)
        if reason:
            return reason

        # 2. Quiet hours (clinic local time)
        reason = _check_quiet_hours(
            self._quiet_start,
            self._quiet_end,
            self._tz,
        )
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

    # -- retry / DLQ --------------------------------------------------------

    def _schedule_retry(
        self,
        action: dict[str, Any],
        aggregate_id: str,
    ) -> None:
        """Schedule action for retry or move to DLQ."""
        attempt = action.get("_retry_count", 0) + 1

        if attempt > self._max_retries:
            # Dead-letter
            action["_retry_count"] = attempt
            self._redis.rpush(
                DLQ_KEY,
                json.dumps(action),
            )  # type: ignore[union-attr]
            self._emit(
                aggregate_id,
                "action_dead_lettered",
                {**action, "reason": "max_retries_exceeded"},
            )
            logger.warning(
                "Action dead-lettered after %d attempts: %s",
                attempt,
                aggregate_id,
            )
            return

        # Exponential backoff via ZSET score = future timestamp
        backoff_idx = min(attempt - 1, len(self._backoff) - 1)
        delay = self._backoff[backoff_idx]
        fire_at = time.time() + delay

        action["_retry_count"] = attempt
        self._redis.zadd(
            RETRY_ZSET,
            {json.dumps(action): fire_at},
        )  # type: ignore[union-attr]
        self._emit(
            aggregate_id,
            "action_retry_scheduled",
            {
                "attempt": attempt,
                "delay_seconds": delay,
                "appointment_id": action.get("appointment_id"),
            },
        )
        logger.info(
            "Retry #%d in %ds for %s",
            attempt,
            delay,
            aggregate_id,
        )

    def process_retries(self) -> int:
        """Re-enqueue actions whose retry time has arrived.

        Returns the number of actions moved back to the main queue.
        """
        now = time.time()
        # Grab items with score <= now
        items = self._redis.zrangebyscore(
            RETRY_ZSET,
            0,
            now,
        )  # type: ignore[union-attr]
        if not items:
            return 0
        moved = 0
        for raw in items:
            self._redis.zrem(RETRY_ZSET, raw)  # type: ignore[union-attr]
            self._redis.rpush(QUEUE_NAME, raw)  # type: ignore[union-attr]
            moved += 1
        logger.info("Re-enqueued %d retries", moved)
        return moved

    def dlq_size(self) -> int:
        """Return current DLQ depth."""
        return self._redis.llen(DLQ_KEY)  # type: ignore[union-attr,return-value]

    def replay_dlq(
        self,
        max_items: int = 100,
    ) -> int:
        """Move items from DLQ back to main queue.

        Resets retry count. Returns number of items replayed.
        """
        replayed = 0
        for _ in range(max_items):
            raw = self._redis.lpop(DLQ_KEY)  # type: ignore[union-attr]
            if raw is None:
                break
            action: dict[str, Any] = json.loads(
                raw,  # type: ignore[arg-type]
            )
            action["_retry_count"] = 0
            self._redis.rpush(
                QUEUE_NAME,
                json.dumps(action),
            )  # type: ignore[union-attr]
            replayed += 1
        logger.info("Replayed %d items from DLQ", replayed)
        return replayed

    # -- execute ------------------------------------------------------------

    def _execute(self, action: dict[str, Any]) -> dict[str, Any] | None:
        """Execute a single action via adapter, emit audit event."""
        action_type = action.get("action_type", "unknown")
        aggregate_id = action.get("appointment_id") or action.get(
            "pr_number",
            "unknown",
        )
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

        # -- Dedup per appointment+channel (after rails, before adapter) --
        dedup_reason = _check_dedup(
            action,
            self._redis,
            self._dedup_ttl,
        )
        if dedup_reason:
            logger.info(
                "Action deduplicated: %s channel=%s",
                aggregate_id,
                action.get("channel", "sms"),
            )
            self._emit(
                aggregate_id,
                "action_blocked",
                {**action, "reason": dedup_reason},
            )
            return {"blocked": True, "reason": dedup_reason}

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
            # Schedule retry instead of silently dropping
            self._schedule_retry(action, aggregate_id)
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
        """Blocking loop — dequeue actions until stopped.

        Also checks the retry ZSET each iteration.
        """
        logger.info(
            "Worker started, listening on queue: %s",
            QUEUE_NAME,
        )
        while True:
            # Promote due retries before blocking
            self.process_retries()

            result = self._redis.blpop(
                [QUEUE_NAME],
                timeout=int(timeout),
            )
            if result is None:
                continue
            _, raw = result  # type: ignore[misc]
            action: dict[str, Any] = json.loads(
                raw,  # type: ignore[arg-type]
            )
            self._execute(action)
