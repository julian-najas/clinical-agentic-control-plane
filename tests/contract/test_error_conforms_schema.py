"""Contract tests: runtime API errors must conform to local error schema."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from httpx import ASGITransport, AsyncClient

from cacp.api.app import create_app


def _load_error_schema() -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[2]
    schema_path = repo_root / "specs" / "contracts" / "error.schema.json"
    return json.loads(schema_path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


@pytest.mark.anyio
async def test_422_validation_error_conforms_local_schema() -> None:
    schema = _load_error_schema()
    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/ingest", json={"appointment_id": "X"})

    assert resp.status_code == 422
    payload = resp.json()
    jsonschema.validate(instance=payload, schema=schema)


@pytest.mark.anyio
async def test_404_http_error_conforms_local_schema() -> None:
    schema = _load_error_schema()
    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/does-not-exist")

    assert resp.status_code == 404
    payload = resp.json()
    jsonschema.validate(instance=payload, schema=schema)


@pytest.mark.anyio
async def test_500_unhandled_error_conforms_local_schema() -> None:
    schema = _load_error_schema()
    app = create_app()

    @app.get("/__contract_boom")
    async def boom() -> dict[str, str]:
        raise RuntimeError("boom")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/__contract_boom")

    assert resp.status_code == 500
    payload = resp.json()
    jsonschema.validate(instance=payload, schema=schema)
