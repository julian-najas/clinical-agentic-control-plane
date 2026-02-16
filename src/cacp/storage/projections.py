"""Read-model projections from the event store."""

from __future__ import annotations

from typing import Any

__all__ = ["NoShowProjection"]


class NoShowProjection:
    """Projects no-show statistics from events."""

    def __init__(self) -> None:
        self._stats: dict[str, Any] = {}

    def project(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        """Build a summary from events.

        Returns:
            Dict with total_appointments, no_shows, no_show_rate, etc.
        """
        total = 0
        no_shows = 0
        confirmed = 0
        rescheduled = 0

        for event in events:
            etype = event.get("event_type", "")
            if etype == "appointment_ingested":
                total += 1
            elif etype == "no_show_recorded":
                no_shows += 1
            elif etype == "appointment_confirmed":
                confirmed += 1
            elif etype == "appointment_rescheduled":
                rescheduled += 1

        rate = no_shows / total if total > 0 else 0.0

        return {
            "total_appointments": total,
            "no_shows": no_shows,
            "confirmed": confirmed,
            "rescheduled": rescheduled,
            "no_show_rate": round(rate, 4),
        }
