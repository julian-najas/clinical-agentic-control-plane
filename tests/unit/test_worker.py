"""Tests for worker — noop adapter + event emission."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

from cacp.storage.event_store import InMemoryEventStore
from cacp.workers.worker import NoopAdapter, Worker


def _mock_redis(queue_items: list[dict[str, Any]]) -> MagicMock:
    """Create a mock Redis with pre-loaded queue items."""
    mock = MagicMock()
    encoded = [json.dumps(item) for item in queue_items]
    mock.lpop.side_effect = encoded + [None]
    return mock


class TestNoopAdapter:
    def test_execute_returns_metadata(self) -> None:
        adapter = NoopAdapter()
        result = adapter.execute({"action_type": "send_reminder", "appointment_id": "APT-1"})
        assert result["adapter"] == "noop"
        assert result["status"] == "executed"
        assert result["action_type"] == "send_reminder"


class TestWorker:
    def setup_method(self) -> None:
        self.event_store = InMemoryEventStore()

    def test_run_once_executes_and_emits_event(self) -> None:
        action = {
            "action_type": "execute_plan",
            "appointment_id": "APT-100",
            "pr_number": 42,
        }
        redis_mock = _mock_redis([action])
        worker = Worker(
            redis_client=redis_mock,
            event_store=self.event_store,
        )

        result = worker.run_once()
        assert result is not None
        assert result["action_type"] == "execute_plan"

        # Verify action_executed event
        events = self.event_store.list_events(aggregate_id="APT-100")
        assert len(events) == 1
        assert events[0]["event_type"] == "action_executed"
        assert events[0]["payload"]["adapter"] == "noop"

    def test_run_once_no_adapter_emits_failed(self) -> None:
        action = {
            "action_type": "unknown_type",
            "appointment_id": "APT-200",
        }
        redis_mock = _mock_redis([action])
        worker = Worker(
            redis_client=redis_mock,
            adapters={},  # no adapters registered
            event_store=self.event_store,
        )

        result = worker.run_once()
        assert result is not None

        events = self.event_store.list_events(aggregate_id="APT-200")
        assert len(events) == 1
        assert events[0]["event_type"] == "action_failed"
        assert events[0]["payload"]["reason"] == "no_adapter"

    def test_run_once_empty_queue_returns_none(self) -> None:
        redis_mock = _mock_redis([])
        worker = Worker(redis_client=redis_mock, event_store=self.event_store)

        result = worker.run_once()
        assert result is None

    def test_adapter_exception_emits_failed(self) -> None:
        class FailingAdapter:
            def execute(self, action: dict[str, Any]) -> dict[str, Any]:
                msg = "boom"
                raise RuntimeError(msg)

        action = {"action_type": "explode", "appointment_id": "APT-300"}
        redis_mock = _mock_redis([action])
        worker = Worker(
            redis_client=redis_mock,
            adapters={"explode": FailingAdapter()},  # type: ignore[dict-item]
            event_store=self.event_store,
        )

        result = worker.run_once()
        assert result is not None

        events = self.event_store.list_events(aggregate_id="APT-300")
        assert len(events) == 1
        assert events[0]["event_type"] == "action_failed"
        assert events[0]["payload"]["reason"] == "adapter_error"
