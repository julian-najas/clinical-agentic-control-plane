"""Tests for GitHub webhook endpoint — signature, idempotency, filtering."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from cacp.api.app import create_app
from cacp.settings import Settings
from cacp.storage.event_store import InMemoryEventStore

WEBHOOK_SECRET = "test-webhook-secret"


def _sign(payload: bytes, secret: str) -> str:
    """Compute X-Hub-Signature-256 for a payload."""
    return "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def _merged_pr_payload(
    pr_number: int = 42,
    repo_name: str = "clinic-gitops-config",
    appointment_id: str = "APT-100",
) -> dict[str, Any]:
    return {
        "action": "closed",
        "pull_request": {
            "number": pr_number,
            "merged": True,
            "merge_commit_sha": "abc123def456",
            "title": f"proposal/abcd1234 — {appointment_id}",
            "body": f"appointment_id: {appointment_id}\nenvironment: dev",
        },
        "repository": {"name": repo_name, "full_name": f"julian-najas/{repo_name}"},
    }


@pytest.fixture()
def app_with_webhook() -> Any:
    a = create_app()
    settings = Settings(
        github_webhook_secret=WEBHOOK_SECRET,
        pg_dsn="",
        redis_url="redis://localhost:6379/0",
        opa_url="http://localhost:8181",
    )
    a.state.settings = settings
    a.state.event_store = InMemoryEventStore()
    # Mock Redis for idempotency + enqueue
    mock_redis = MagicMock()
    mock_redis.set.return_value = True  # first call → new
    mock_redis.rpush.return_value = 1
    a.state.redis_client = mock_redis
    return a


# ── Valid merged PR → 202 ───────────────────────────────


@pytest.mark.anyio()
async def test_valid_merged_pr_accepted(app_with_webhook: Any) -> None:
    payload = _merged_pr_payload()
    body = json.dumps(payload).encode()
    sig = _sign(body, WEBHOOK_SECRET)

    async with AsyncClient(
        transport=ASGITransport(app=app_with_webhook),
        base_url="http://test",
    ) as client:
        resp = await client.post(
            "/webhook/github",
            content=body,
            headers={
                "x-github-event": "pull_request",
                "x-hub-signature-256": sig,
                "x-github-delivery": "delivery-001",
                "content-type": "application/json",
            },
        )

    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "accepted"
    assert "PR #42" in data["message"]

    # Verify event was emitted
    events = app_with_webhook.state.event_store.list_events(event_type="pr_merged")
    assert len(events) == 1
    assert events[0]["payload"]["pr_number"] == 42


# ── Invalid signature → 401 ─────────────────────────────


@pytest.mark.anyio()
async def test_invalid_signature_rejected(app_with_webhook: Any) -> None:
    payload = _merged_pr_payload()
    body = json.dumps(payload).encode()

    async with AsyncClient(
        transport=ASGITransport(app=app_with_webhook),
        base_url="http://test",
    ) as client:
        resp = await client.post(
            "/webhook/github",
            content=body,
            headers={
                "x-github-event": "pull_request",
                "x-hub-signature-256": "sha256=invalid",
                "x-github-delivery": "delivery-002",
                "content-type": "application/json",
            },
        )

    assert resp.status_code == 401


# ── Duplicate delivery → 200 (idempotent) ───────────────


@pytest.mark.anyio()
async def test_duplicate_delivery_idempotent(app_with_webhook: Any) -> None:
    # Simulate Redis SETNX returning False (already seen)
    app_with_webhook.state.redis_client.set.return_value = False

    payload = _merged_pr_payload()
    body = json.dumps(payload).encode()
    sig = _sign(body, WEBHOOK_SECRET)

    async with AsyncClient(
        transport=ASGITransport(app=app_with_webhook),
        base_url="http://test",
    ) as client:
        resp = await client.post(
            "/webhook/github",
            content=body,
            headers={
                "x-github-event": "pull_request",
                "x-hub-signature-256": sig,
                "x-github-delivery": "delivery-003",
                "content-type": "application/json",
            },
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "duplicate"


# ── PR not merged → ignored ─────────────────────────────


@pytest.mark.anyio()
async def test_pr_not_merged_ignored(app_with_webhook: Any) -> None:
    payload = _merged_pr_payload()
    payload["pull_request"]["merged"] = False
    body = json.dumps(payload).encode()
    sig = _sign(body, WEBHOOK_SECRET)

    async with AsyncClient(
        transport=ASGITransport(app=app_with_webhook),
        base_url="http://test",
    ) as client:
        resp = await client.post(
            "/webhook/github",
            content=body,
            headers={
                "x-github-event": "pull_request",
                "x-hub-signature-256": sig,
                "x-github-delivery": "delivery-004",
                "content-type": "application/json",
            },
        )

    assert resp.status_code == 202
    assert resp.json()["status"] == "ignored"


# ── Non-PR event → ignored ──────────────────────────────


@pytest.mark.anyio()
async def test_non_pr_event_ignored(app_with_webhook: Any) -> None:
    body = json.dumps({"action": "created"}).encode()
    sig = _sign(body, WEBHOOK_SECRET)

    async with AsyncClient(
        transport=ASGITransport(app=app_with_webhook),
        base_url="http://test",
    ) as client:
        resp = await client.post(
            "/webhook/github",
            content=body,
            headers={
                "x-github-event": "push",
                "x-hub-signature-256": sig,
                "x-github-delivery": "delivery-005",
                "content-type": "application/json",
            },
        )

    assert resp.status_code == 202
    assert resp.json()["status"] == "ignored"


# ── Wrong repo → ignored ────────────────────────────────


@pytest.mark.anyio()
async def test_wrong_repo_ignored(app_with_webhook: Any) -> None:
    payload = _merged_pr_payload(repo_name="some-other-repo")
    body = json.dumps(payload).encode()
    sig = _sign(body, WEBHOOK_SECRET)

    async with AsyncClient(
        transport=ASGITransport(app=app_with_webhook),
        base_url="http://test",
    ) as client:
        resp = await client.post(
            "/webhook/github",
            content=body,
            headers={
                "x-github-event": "pull_request",
                "x-hub-signature-256": sig,
                "x-github-delivery": "delivery-006",
                "content-type": "application/json",
            },
        )

    assert resp.status_code == 202
    assert resp.json()["status"] == "ignored"
