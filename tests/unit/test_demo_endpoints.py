"""Tests for demo API endpoints (Sprint 5)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from cacp.api.app import create_app
from cacp.settings import Settings
from cacp.storage.event_store import InMemoryEventStore


@pytest.fixture()
def demo_app() -> Any:
    """Create app for demo endpoint testing."""
    a = create_app()
    settings = Settings(hmac_secret="test", github_token="")
    event_store = InMemoryEventStore()
    a.state.settings = settings
    a.state.event_store = event_store
    a.state.orchestrator = MagicMock()
    return a


@pytest.mark.asyncio()
async def test_dental_roi_defaults(demo_app: Any) -> None:
    transport = ASGITransport(app=demo_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/demo/dental-roi")

    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"]["total_appointments"] == 800
    assert body["roi"]["net_gain_monthly_eur"] > 0
    assert "executive_summary" in body


@pytest.mark.asyncio()
async def test_dental_roi_custom_params(demo_app: Any) -> None:
    transport = ASGITransport(app=demo_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get(
            "/demo/dental-roi",
            params={"citas": 500, "no_show": 0.10, "reduction": 0.30, "seed": 99},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"]["total_appointments"] == 500


@pytest.mark.asyncio()
async def test_dental_roi_csv_download(demo_app: Any) -> None:
    transport = ASGITransport(app=demo_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/demo/dental-roi/csv")

    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "attachment" in resp.headers["content-disposition"]

    lines = resp.text.strip().split("\n")
    # Header + 800 data rows
    assert len(lines) == 801
    assert "appointment_id" in lines[0]


@pytest.mark.asyncio()
async def test_dental_roi_csv_custom_count(demo_app: Any) -> None:
    transport = ASGITransport(app=demo_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/demo/dental-roi/csv", params={"citas": 50})

    assert resp.status_code == 200
    lines = resp.text.strip().split("\n")
    assert len(lines) == 51  # header + 50 rows


@pytest.mark.asyncio()
async def test_dental_roi_validation_error(demo_app: Any) -> None:
    transport = ASGITransport(app=demo_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/demo/dental-roi", params={"citas": 0})

    assert resp.status_code == 422  # FastAPI validation
