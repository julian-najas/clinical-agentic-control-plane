"""Tests for dedup, retry, and DLQ worker functionality (Sprint 4)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

from cacp.consent import InMemoryConsentStore
from cacp.storage.event_store import InMemoryEventStore
from cacp.workers.worker import DLQ_KEY, RETRY_ZSET, Worker


def _mock_redis(
    queue_items: list[dict[str, Any]],
) -> MagicMock:
    """Create a mock Redis with pre-loaded queue items."""
    mock = MagicMock()
    encoded = [json.dumps(item) for item in queue_items]
    mock.lpop.side_effect = encoded + [None]
    # Rate-limit pipeline stub
    pipe_mock = MagicMock()
    pipe_mock.execute.return_value = [None, 0, None, None]
    mock.pipeline.return_value = pipe_mock
    # Dedup stub — acquire by default
    mock.set.return_value = True
    # Retry ZSET — empty by default
    mock.zrangebyscore.return_value = []
    # DLQ
    mock.llen.return_value = 0
    return mock


def _action(
    appointment_id: str = "APT-100",
    patient_id: str = "PAT-001",
    channel: str = "sms",
) -> dict[str, Any]:
    return {
        "action_type": "execute_plan",
        "appointment_id": appointment_id,
        "patient_id": patient_id,
        "channel": channel,
    }


class TestDedup:
    """Duplicate actions for same appointment+channel are blocked."""

    def test_duplicate_blocked(self) -> None:
        store = InMemoryConsentStore()
        store.grant("PAT-001", "sms")
        event_store = InMemoryEventStore()
        redis_mock = _mock_redis([_action()])
        # Simulate dedup key already exists
        redis_mock.set.return_value = False

        with patch("cacp.workers.worker.datetime") as mock_dt:
            mock_now = MagicMock()
            mock_now.hour = 14
            mock_dt.now.return_value = mock_now

            worker = Worker(
                redis_client=redis_mock,
                event_store=event_store,
                consent_store=store,
                timezone="Europe/Madrid",
            )
            result = worker.run_once()

        assert result is not None
        events = event_store.list_events(aggregate_id="APT-100")
        assert any(
            e["event_type"] == "action_blocked" and e["payload"]["reason"] == "duplicate_action"
            for e in events
        )

    def test_first_send_acquires_dedup_key(self) -> None:
        store = InMemoryConsentStore()
        store.grant("PAT-001", "sms")
        event_store = InMemoryEventStore()
        redis_mock = _mock_redis([_action()])
        redis_mock.set.return_value = True  # First time → acquired

        with patch("cacp.workers.worker.datetime") as mock_dt:
            mock_now = MagicMock()
            mock_now.hour = 14
            mock_dt.now.return_value = mock_now

            worker = Worker(
                redis_client=redis_mock,
                event_store=event_store,
                consent_store=store,
                timezone="Europe/Madrid",
            )
            result = worker.run_once()

        assert result is not None
        events = event_store.list_events(aggregate_id="APT-100")
        assert any(e["event_type"] == "action_executed" for e in events)
        # Verify redis.set was called with nx and ex
        redis_mock.set.assert_called_once()
        call_kwargs = redis_mock.set.call_args
        assert call_kwargs[1]["nx"] is True
        assert call_kwargs[1]["ex"] > 0


class TestRetryBackoff:
    """Failed actions are retried with exponential backoff."""

    def test_adapter_failure_schedules_retry(self) -> None:
        class FailingAdapter:
            def execute(self, action: dict[str, Any]) -> dict[str, Any]:
                msg = "twilio down"
                raise RuntimeError(msg)

        event_store = InMemoryEventStore()
        redis_mock = _mock_redis([_action()])

        worker = Worker(
            redis_client=redis_mock,
            adapters={"execute_plan": FailingAdapter()},  # type: ignore[dict-item]
            event_store=event_store,
            consent_store=None,
            quiet_hours_start=0,
            quiet_hours_end=0,
            max_retries=3,
            retry_backoff=[60, 300, 900],
        )
        worker.run_once()

        events = event_store.list_events(aggregate_id="APT-100")
        assert any(e["event_type"] == "action_retry_scheduled" for e in events)
        # Verify zadd was called on RETRY_ZSET
        redis_mock.zadd.assert_called_once()

    def test_max_retries_dead_letters(self) -> None:
        class FailingAdapter:
            def execute(self, action: dict[str, Any]) -> dict[str, Any]:
                msg = "still down"
                raise RuntimeError(msg)

        event_store = InMemoryEventStore()
        action = _action()
        action["_retry_count"] = 3  # Already at max
        redis_mock = _mock_redis([action])

        worker = Worker(
            redis_client=redis_mock,
            adapters={"execute_plan": FailingAdapter()},  # type: ignore[dict-item]
            event_store=event_store,
            consent_store=None,
            quiet_hours_start=0,
            quiet_hours_end=0,
            max_retries=3,
        )
        worker.run_once()

        events = event_store.list_events(aggregate_id="APT-100")
        assert any(e["event_type"] == "action_dead_lettered" for e in events)
        # Verify rpush to DLQ
        redis_mock.rpush.assert_called()
        dlq_calls = [c for c in redis_mock.rpush.call_args_list if c[0][0] == DLQ_KEY]
        assert len(dlq_calls) == 1


class TestProcessRetries:
    """Retry queue promotes due items back to main queue."""

    def test_process_retries_moves_items(self) -> None:
        redis_mock = MagicMock()
        action_json = json.dumps(_action())
        redis_mock.zrangebyscore.return_value = [action_json]
        redis_mock.zrem.return_value = 1
        redis_mock.rpush.return_value = 1

        worker = Worker(redis_client=redis_mock)
        moved = worker.process_retries()

        assert moved == 1
        redis_mock.zrem.assert_called_once_with(RETRY_ZSET, action_json)

    def test_process_retries_empty(self) -> None:
        redis_mock = MagicMock()
        redis_mock.zrangebyscore.return_value = []

        worker = Worker(redis_client=redis_mock)
        moved = worker.process_retries()
        assert moved == 0


class TestReplayDLQ:
    """DLQ replay moves items back to main queue with reset retry count."""

    def test_replay_resets_retry_count(self) -> None:
        action = _action()
        action["_retry_count"] = 3
        redis_mock = MagicMock()
        redis_mock.lpop.side_effect = [json.dumps(action), None]

        worker = Worker(redis_client=redis_mock)
        replayed = worker.replay_dlq(max_items=10)

        assert replayed == 1
        # Check the replayed action has _retry_count=0
        rpush_call = redis_mock.rpush.call_args
        replayed_action = json.loads(rpush_call[0][1])
        assert replayed_action["_retry_count"] == 0

    def test_replay_empty_dlq(self) -> None:
        redis_mock = MagicMock()
        redis_mock.lpop.return_value = None

        worker = Worker(redis_client=redis_mock)
        replayed = worker.replay_dlq()
        assert replayed == 0
