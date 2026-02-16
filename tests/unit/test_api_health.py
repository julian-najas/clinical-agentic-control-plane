"""Tests for the API health endpoint."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from cacp.api.app import create_app


@pytest.mark.anyio()
async def test_health_returns_ok() -> None:
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
