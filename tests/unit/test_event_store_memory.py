"""Tests for the event store (in-memory + idempotency)."""

from __future__ import annotations

from cacp.storage.event_store import InMemoryEventStore


class TestInMemoryEventStore:
    def setup_method(self) -> None:
        self.store = InMemoryEventStore()

    def test_append_and_list(self) -> None:
        eid = self.store.append("AGG-1", "test_event", {"key": "value"})
        assert eid
        events = self.store.list_events(aggregate_id="AGG-1")
        assert len(events) == 1
        assert events[0]["event_type"] == "test_event"
        assert events[0]["payload"] == {"key": "value"}

    def test_list_filters_by_aggregate(self) -> None:
        self.store.append("AGG-1", "evt_a", {})
        self.store.append("AGG-2", "evt_b", {})
        self.store.append("AGG-1", "evt_c", {})

        events = self.store.list_events(aggregate_id="AGG-1")
        assert len(events) == 2
        types = {e["event_type"] for e in events}
        assert types == {"evt_a", "evt_c"}

    def test_list_filters_by_type(self) -> None:
        self.store.append("AGG-1", "risk_scored", {"score": 0.5})
        self.store.append("AGG-1", "pr_opened", {"url": "..."})

        events = self.store.list_events(event_type="risk_scored")
        assert len(events) == 1
        assert events[0]["event_type"] == "risk_scored"

    def test_idempotency_key_prevents_duplicates(self) -> None:
        eid1 = self.store.append("AGG-1", "evt", {"a": 1}, idempotency_key="KEY-1")
        eid2 = self.store.append("AGG-1", "evt", {"a": 2}, idempotency_key="KEY-1")

        assert eid1 == eid2
        events = self.store.list_events(aggregate_id="AGG-1")
        assert len(events) == 1
        assert events[0]["payload"] == {"a": 1}  # first write wins

    def test_different_idempotency_keys_both_stored(self) -> None:
        self.store.append("AGG-1", "evt", {"a": 1}, idempotency_key="KEY-1")
        self.store.append("AGG-1", "evt", {"a": 2}, idempotency_key="KEY-2")

        events = self.store.list_events(aggregate_id="AGG-1")
        assert len(events) == 2

    def test_list_respects_limit(self) -> None:
        for i in range(10):
            self.store.append("AGG-1", "evt", {"i": i})
        events = self.store.list_events(aggregate_id="AGG-1", limit=3)
        assert len(events) == 3

    def test_empty_store_returns_empty(self) -> None:
        events = self.store.list_events()
        assert events == []
