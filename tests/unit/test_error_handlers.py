"""Tests for global API error handlers."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from cacp.api.app import create_app


@pytest.mark.anyio()
async def test_validation_error_returns_machine_readable_payload() -> None:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/ingest", json={"appointment_id": "X"})

    assert resp.status_code == 422
    body = resp.json()
    assert body["error_code"] == "INVALID_REQUEST"
    assert body["message"] == "Request validation failed"
    assert body["request_id"]
    assert isinstance(body.get("details"), list)
    assert resp.headers["x-correlation-id"] == body["request_id"]


@pytest.mark.anyio()
async def test_not_found_uses_invalid_request_error_code() -> None:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/does-not-exist")

    assert resp.status_code == 404
    body = resp.json()
    assert body["error_code"] == "INVALID_REQUEST"
    assert body["request_id"]


@pytest.mark.anyio()
async def test_unhandled_exception_returns_internal_error_payload() -> None:
    app = create_app()

    @app.get("/__boom")
    async def boom() -> dict[str, str]:
        raise RuntimeError("boom")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/__boom")

    assert resp.status_code == 500
    body = resp.json()
    assert body["error_code"] == "INTERNAL_ERROR"
    assert body["message"] == "Internal server error"
    assert body["request_id"]
