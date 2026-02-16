"""Append-only event store — protocol + implementations."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    import psycopg

__all__ = ["EventStoreProtocol", "InMemoryEventStore", "PostgresEventStore"]


class EventStoreProtocol(Protocol):
    """Minimal contract for an append-only event store."""

    def append(
        self,
        aggregate_id: str,
        event_type: str,
        payload: dict[str, Any],
        actor: str = "system",
        idempotency_key: str | None = None,
    ) -> str:
        """Append an event. Returns the event_id."""
        ...

    def list_events(
        self,
        aggregate_id: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Retrieve events, optionally filtered."""
        ...


# ── In-memory implementation (dev / tests) ──────────────


class InMemoryEventStore:
    """Append-only store backed by a plain list — no external deps."""

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []
        self._seen_keys: set[str] = set()

    def append(
        self,
        aggregate_id: str,
        event_type: str,
        payload: dict[str, Any],
        actor: str = "system",
        idempotency_key: str | None = None,
    ) -> str:
        if idempotency_key and idempotency_key in self._seen_keys:
            # Idempotent — return existing event_id
            for evt in self._events:
                if evt.get("idempotency_key") == idempotency_key:
                    return evt["event_id"]  # type: ignore[no-any-return]
            return ""  # pragma: no cover
        event_id = str(uuid.uuid4())
        record: dict[str, Any] = {
            "event_id": event_id,
            "aggregate_id": aggregate_id,
            "event_type": event_type,
            "payload": payload,
            "actor": actor,
            "created_at": datetime.now(UTC).isoformat(),
        }
        if idempotency_key:
            record["idempotency_key"] = idempotency_key
            self._seen_keys.add(idempotency_key)
        self._events.append(record)
        return event_id

    def list_events(
        self,
        aggregate_id: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        out = self._events
        if aggregate_id:
            out = [e for e in out if e["aggregate_id"] == aggregate_id]
        if event_type:
            out = [e for e in out if e["event_type"] == event_type]
        return list(reversed(out))[:limit]


# ── PostgreSQL implementation ────────────────────────────


class PostgresEventStore:
    """Append-only event log in PostgreSQL."""

    def __init__(self, conn: psycopg.Connection[Any]) -> None:
        self._conn = conn

    def append(
        self,
        aggregate_id: str,
        event_type: str,
        payload: dict[str, Any],
        actor: str = "system",
        idempotency_key: str | None = None,
    ) -> str:
        event_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()

        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO events
                    (event_id, aggregate_id, event_type,
                     payload, actor, created_at, idempotency_key)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (idempotency_key) DO NOTHING
                """,
                (
                    event_id,
                    aggregate_id,
                    event_type,
                    json.dumps(payload),
                    actor,
                    now,
                    idempotency_key,
                ),
            )
        self._conn.commit()
        return event_id

    def list_events(
        self,
        aggregate_id: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []

        if aggregate_id:
            clauses.append("aggregate_id = %s")
            params.append(aggregate_id)
        if event_type:
            clauses.append("event_type = %s")
            params.append(event_type)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)

        with self._conn.cursor() as cur:
            cur.execute(
                f"SELECT event_id, aggregate_id, event_type, payload, actor, created_at "  # noqa: S608
                f"FROM events {where} ORDER BY created_at DESC LIMIT %s",
                params,
            )
            rows = cur.fetchall()

        return [
            {
                "event_id": r[0],
                "aggregate_id": r[1],
                "event_type": r[2],
                "payload": json.loads(r[3]) if isinstance(r[3], str) else r[3],
                "actor": r[4],
                "created_at": r[5],
            }
            for r in rows
        ]
