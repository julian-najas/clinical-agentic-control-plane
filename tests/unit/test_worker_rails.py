"""Tests for worker compliance rails (consent, quiet hours, rate limit)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

from cacp.consent import InMemoryConsentStore
from cacp.storage.event_store import InMemoryEventStore
from cacp.workers.worker import Worker


def _mock_redis(
    queue_items: list[dict[str, Any]],
) -> MagicMock:
    """Create a mock Redis with pre-loaded queue items."""
    mock = MagicMock()
    encoded = [json.dumps(item) for item in queue_items]
    mock.lpop.side_effect = encoded + [None]
    # Rate-limit pipeline mock: [zremrangebyscore, zcard=0, zadd, expire]
    pipe_mock = MagicMock()
    pipe_mock.execute.return_value = [None, 0, None, None]
    mock.pipeline.return_value = pipe_mock
    return mock


def _action(
    patient_id: str = "PAT-001",
    channel: str = "sms",
) -> dict[str, Any]:
    return {
        "action_type": "execute_plan",
        "appointment_id": "APT-100",
        "patient_id": patient_id,
        "channel": channel,
    }


class TestConsentRail:
    """Actions without consent should be blocked."""

    def test_blocked_without_consent(self) -> None:
        store = InMemoryConsentStore()
        event_store = InMemoryEventStore()
        redis_mock = _mock_redis([_action()])

        worker = Worker(
            redis_client=redis_mock,
            event_store=event_store,
            consent_store=store,
        )
        result = worker.run_once()
        assert result is not None

        events = event_store.list_events(aggregate_id="APT-100")
        assert len(events) == 1
        assert events[0]["event_type"] == "action_blocked"
        assert events[0]["payload"]["reason"] == "no_consent"

    def test_allowed_with_consent(self) -> None:
        store = InMemoryConsentStore()
        store.grant("PAT-001", "sms")
        event_store = InMemoryEventStore()
        redis_mock = _mock_redis([_action()])

        worker = Worker(
            redis_client=redis_mock,
            event_store=event_store,
            consent_store=store,
        )
        result = worker.run_once()
        assert result is not None

        events = event_store.list_events(aggregate_id="APT-100")
        assert any(e["event_type"] == "action_executed" for e in events)

    def test_no_consent_store_allows_through(self) -> None:
        """When consent_store is None, skip the check."""
        event_store = InMemoryEventStore()
        redis_mock = _mock_redis([_action()])

        worker = Worker(
            redis_client=redis_mock,
            event_store=event_store,
            consent_store=None,
        )
        result = worker.run_once()
        assert result is not None

        events = event_store.list_events(aggregate_id="APT-100")
        assert any(e["event_type"] == "action_executed" for e in events)


class TestQuietHoursRail:
    """Actions during quiet hours should be blocked."""

    def test_blocked_during_quiet_hours(self) -> None:
        store = InMemoryConsentStore()
        store.grant("PAT-001", "sms")
        event_store = InMemoryEventStore()
        redis_mock = _mock_redis([_action()])

        # Patch datetime to return hour=23 (inside 22-08 window)
        with patch("cacp.workers.worker.datetime") as mock_dt:
            mock_now = MagicMock()
            mock_now.hour = 23
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = None

            worker = Worker(
                redis_client=redis_mock,
                event_store=event_store,
                consent_store=store,
                quiet_hours_start=22,
                quiet_hours_end=8,
            )
            result = worker.run_once()

        assert result is not None
        events = event_store.list_events(aggregate_id="APT-100")
        assert any(
            e["event_type"] == "action_blocked" and e["payload"]["reason"] == "quiet_hours"
            for e in events
        )

    def test_allowed_outside_quiet_hours(self) -> None:
        store = InMemoryConsentStore()
        store.grant("PAT-001", "sms")
        event_store = InMemoryEventStore()
        redis_mock = _mock_redis([_action()])

        # Patch datetime to return hour=14 (outside 22-08 window)
        with patch("cacp.workers.worker.datetime") as mock_dt:
            mock_now = MagicMock()
            mock_now.hour = 14
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = None

            worker = Worker(
                redis_client=redis_mock,
                event_store=event_store,
                consent_store=store,
                quiet_hours_start=22,
                quiet_hours_end=8,
            )
            result = worker.run_once()

        assert result is not None
        events = event_store.list_events(aggregate_id="APT-100")
        assert any(e["event_type"] == "action_executed" for e in events)


class TestRateLimitRail:
    """Actions beyond rate limit should be blocked."""

    def test_blocked_when_rate_exceeded(self) -> None:
        store = InMemoryConsentStore()
        store.grant("PAT-001", "sms")
        event_store = InMemoryEventStore()
        redis_mock = _mock_redis([_action()])

        # Pipeline returns count >= limit
        pipe_mock = MagicMock()
        pipe_mock.execute.return_value = [None, 3, None, None]
        redis_mock.pipeline.return_value = pipe_mock

        with patch("cacp.workers.worker.datetime") as mock_dt:
            mock_now = MagicMock()
            mock_now.hour = 14
            mock_dt.now.return_value = mock_now

            worker = Worker(
                redis_client=redis_mock,
                event_store=event_store,
                consent_store=store,
                sms_rate_limit=3,
                quiet_hours_start=22,
                quiet_hours_end=8,
            )
            result = worker.run_once()

        assert result is not None
        events = event_store.list_events(aggregate_id="APT-100")
        assert any(
            e["event_type"] == "action_blocked" and e["payload"]["reason"] == "rate_limited"
            for e in events
        )

    def test_allowed_under_rate_limit(self) -> None:
        store = InMemoryConsentStore()
        store.grant("PAT-001", "sms")
        event_store = InMemoryEventStore()
        redis_mock = _mock_redis([_action()])

        # Pipeline returns count=1 (under limit of 3)
        pipe_mock = MagicMock()
        pipe_mock.execute.return_value = [None, 1, None, None]
        redis_mock.pipeline.return_value = pipe_mock

        with patch("cacp.workers.worker.datetime") as mock_dt:
            mock_now = MagicMock()
            mock_now.hour = 14
            mock_dt.now.return_value = mock_now

            worker = Worker(
                redis_client=redis_mock,
                event_store=event_store,
                consent_store=store,
                sms_rate_limit=3,
                quiet_hours_start=22,
                quiet_hours_end=8,
            )
            result = worker.run_once()

        assert result is not None
        events = event_store.list_events(aggregate_id="APT-100")
        assert any(e["event_type"] == "action_executed" for e in events)
