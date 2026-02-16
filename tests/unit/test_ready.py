"""Tests for readiness endpoint with real dependency checks."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from cacp.api.app import create_app
from cacp.settings import Settings


@pytest.fixture()
def app() -> object:
    a = create_app()
    a.state.settings = Settings(
        pg_dsn="postgresql://test", redis_url="redis://test", opa_url="http://test:8181"
    )
    return a


# ── all healthy ─────────────────────────────────────────


@pytest.mark.anyio()
async def test_ready_all_ok(app: object) -> None:
    with (
        patch("cacp.api.routes.health.check_postgres", new_callable=AsyncMock, return_value=True),
        patch("cacp.api.routes.health.check_redis", new_callable=AsyncMock, return_value=True),
        patch("cacp.api.routes.health.check_opa", new_callable=AsyncMock, return_value=True),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),  # type: ignore[arg-type]
            base_url="http://test",
        ) as client:
            resp = await client.get("/ready")

    assert resp.status_code == 200
    body = resp.json()
    assert body["ready"] is True
    assert body["checks"]["postgres"] is True
    assert body["checks"]["redis"] is True
    assert body["checks"]["opa"] is True


# ── postgres down ───────────────────────────────────────


@pytest.mark.anyio()
async def test_ready_postgres_down(app: object) -> None:
    with (
        patch("cacp.api.routes.health.check_postgres", new_callable=AsyncMock, return_value=False),
        patch("cacp.api.routes.health.check_redis", new_callable=AsyncMock, return_value=True),
        patch("cacp.api.routes.health.check_opa", new_callable=AsyncMock, return_value=True),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),  # type: ignore[arg-type]
            base_url="http://test",
        ) as client:
            resp = await client.get("/ready")

    assert resp.status_code == 503
    body = resp.json()
    assert body["ready"] is False
    assert body["checks"]["postgres"] is False


# ── redis down ──────────────────────────────────────────


@pytest.mark.anyio()
async def test_ready_redis_down(app: object) -> None:
    with (
        patch("cacp.api.routes.health.check_postgres", new_callable=AsyncMock, return_value=True),
        patch("cacp.api.routes.health.check_redis", new_callable=AsyncMock, return_value=False),
        patch("cacp.api.routes.health.check_opa", new_callable=AsyncMock, return_value=True),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),  # type: ignore[arg-type]
            base_url="http://test",
        ) as client:
            resp = await client.get("/ready")

    assert resp.status_code == 503
    body = resp.json()
    assert body["ready"] is False
    assert body["checks"]["redis"] is False


# ── opa down ────────────────────────────────────────────


@pytest.mark.anyio()
async def test_ready_opa_down(app: object) -> None:
    with (
        patch("cacp.api.routes.health.check_postgres", new_callable=AsyncMock, return_value=True),
        patch("cacp.api.routes.health.check_redis", new_callable=AsyncMock, return_value=True),
        patch("cacp.api.routes.health.check_opa", new_callable=AsyncMock, return_value=False),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),  # type: ignore[arg-type]
            base_url="http://test",
        ) as client:
            resp = await client.get("/ready")

    assert resp.status_code == 503
    body = resp.json()
    assert body["ready"] is False
    assert body["checks"]["opa"] is False
