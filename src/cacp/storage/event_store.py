"""Append-only event store in PostgreSQL."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import psycopg

__all__ = ["EventStore"]


class EventStore:
    """Append-only event log for audit and replay."""

    def __init__(self, conn: psycopg.Connection[Any]) -> None:
        self._conn = conn

    def append(
        self,
        event_type: str,
        payload: dict[str, Any],
        actor: str = "system",
    ) -> str:
        """Append an event and return its event_id."""
        event_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()

        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO events (event_id, event_type, payload, actor, created_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (event_id, event_type, json.dumps(payload), actor, now),
            )
        self._conn.commit()
        return event_id

    def get_events(
        self,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Retrieve events, optionally filtered by type."""
        with self._conn.cursor() as cur:
            if event_type:
                cur.execute(
                    "SELECT event_id, event_type, payload, actor, created_at "
                    "FROM events WHERE event_type = %s "
                    "ORDER BY created_at DESC LIMIT %s",
                    (event_type, limit),
                )
            else:
                cur.execute(
                    "SELECT event_id, event_type, payload, actor, created_at "
                    "FROM events ORDER BY created_at DESC LIMIT %s",
                    (limit,),
                )
            rows = cur.fetchall()

        return [
            {
                "event_id": r[0],
                "event_type": r[1],
                "payload": json.loads(r[2]) if isinstance(r[2], str) else r[2],
                "actor": r[3],
                "created_at": r[4],
            }
            for r in rows
        ]
