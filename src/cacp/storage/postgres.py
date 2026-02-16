"""PostgreSQL connection management."""

from __future__ import annotations

import psycopg

__all__ = ["get_connection"]


def get_connection(dsn: str) -> psycopg.Connection[tuple[object, ...]]:
    """Create a new PostgreSQL connection."""
    return psycopg.connect(dsn, autocommit=False)
