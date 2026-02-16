"""Tests for event store (requires PostgreSQL — skipped if unavailable)."""

from __future__ import annotations

from cacp.storage.projections import NoShowProjection


class TestNoShowProjection:
    def test_empty_events(self) -> None:
        proj = NoShowProjection()
        result = proj.project([])
        assert result["total_appointments"] == 0
        assert result["no_show_rate"] == 0.0

    def test_calculates_rate(self) -> None:
        events = [
            {"event_type": "appointment_ingested"},
            {"event_type": "appointment_ingested"},
            {"event_type": "appointment_ingested"},
            {"event_type": "appointment_ingested"},
            {"event_type": "no_show_recorded"},
        ]
        proj = NoShowProjection()
        result = proj.project(events)
        assert result["total_appointments"] == 4
        assert result["no_shows"] == 1
        assert result["no_show_rate"] == 0.25

    def test_confirmed_and_rescheduled(self) -> None:
        events = [
            {"event_type": "appointment_ingested"},
            {"event_type": "appointment_confirmed"},
            {"event_type": "appointment_rescheduled"},
        ]
        proj = NoShowProjection()
        result = proj.project(events)
        assert result["confirmed"] == 1
        assert result["rescheduled"] == 1
