"""Real health-check probes for downstream dependencies."""

from __future__ import annotations

import asyncio
import logging
from functools import partial
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    import psycopg
    import redis

__all__ = ["check_postgres", "check_redis", "check_opa"]

logger = logging.getLogger(__name__)

_TIMEOUT = 2  # seconds — fast-fail for readiness


def _sync_check_postgres(dsn: str) -> bool:
    """Blocking SELECT 1 against PostgreSQL."""
    import psycopg as _pg  # noqa: F811

    conn: psycopg.Connection[Any] = _pg.connect(dsn, connect_timeout=_TIMEOUT)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
    finally:
        conn.close()
    return True


async def check_postgres(dsn: str) -> bool:
    """SELECT 1 against PostgreSQL (non-blocking). Returns False on any failure."""
    if not dsn:
        return False
    try:
        return await asyncio.to_thread(partial(_sync_check_postgres, dsn))
    except Exception:
        logger.warning("Postgres health-check failed", exc_info=True)
        return False


def _sync_check_redis(url: str) -> bool:
    """Blocking PING against Redis."""
    import redis as _redis  # noqa: F811

    client: redis.Redis = _redis.Redis.from_url(  # type: ignore[type-arg]
        url,
        socket_timeout=_TIMEOUT,
        socket_connect_timeout=_TIMEOUT,
    )
    try:
        client.ping()
    finally:
        client.close()
    return True


async def check_redis(url: str) -> bool:
    """PING the Redis instance (non-blocking). Returns False on any failure."""
    if not url:
        return False
    try:
        return await asyncio.to_thread(partial(_sync_check_redis, url))
    except Exception:
        logger.warning("Redis health-check failed", exc_info=True)
        return False


async def check_opa(url: str) -> bool:
    """POST a minimal query to OPA. Returns False on any failure."""
    if not url:
        return False
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{url}/v1/data/health",
                json={"input": {}},
            )
            return resp.status_code == 200  # noqa: TRY300
    except Exception:
        logger.warning("OPA health-check failed", exc_info=True)
        return False
