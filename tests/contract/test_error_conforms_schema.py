"""Contract tests: runtime API errors must conform to local error schema."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from httpx import ASGITransport, AsyncClient

from cacp.api.app import create_app
from cacp.settings import Settings


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


@pytest.mark.anyio
async def test_github_invalid_signature_conforms_local_schema() -> None:
    schema = _load_error_schema()
    app = create_app()
    app.state.settings = Settings(github_webhook_secret="test-webhook-secret")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/webhook/github",
            content=b"{}",
            headers={
                "x-github-event": "pull_request",
                "x-hub-signature-256": "sha256=invalid",
                "content-type": "application/json",
            },
        )

    assert resp.status_code == 401
    payload = resp.json()
    assert payload["error_code"] == "SIGNATURE_INVALID"
    jsonschema.validate(instance=payload, schema=schema)


@pytest.mark.anyio
async def test_twilio_invalid_signature_conforms_local_schema() -> None:
    schema = _load_error_schema()
    app = create_app()
    app.state.settings = Settings(twilio_auth_token="test-twilio-token")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/webhook/twilio-status",
            data={"MessageSid": "SM_TEST_123", "MessageStatus": "delivered", "To": "+34600111222"},
            headers={"X-Twilio-Signature": "invalid"},
        )

    assert resp.status_code == 401
    payload = resp.json()
    assert payload["error_code"] == "SIGNATURE_INVALID"
    jsonschema.validate(instance=payload, schema=schema)
