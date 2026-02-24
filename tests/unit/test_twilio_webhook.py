"""Tests for Twilio delivery-status webhook (Sprint 4)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from cacp.api.app import create_app
from cacp.settings import Settings
from cacp.storage.event_store import InMemoryEventStore


@pytest.fixture()
def app_with_event_store() -> tuple[Any, InMemoryEventStore]:
    """Create app with accessible event store."""
    a = create_app()
    settings = Settings(
        hmac_secret="test",
        github_token="",
        twilio_auth_token="",  # disable signature check for tests
    )
    event_store = InMemoryEventStore()
    a.state.settings = settings
    a.state.event_store = event_store
    a.state.orchestrator = MagicMock()
    return a, event_store


@pytest.mark.asyncio()
async def test_delivered_status(
    app_with_event_store: tuple[Any, InMemoryEventStore],
) -> None:
    app, event_store = app_with_event_store
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post(
            "/webhook/twilio-status",
            data={
                "MessageSid": "SM_TEST_123",
                "MessageStatus": "delivered",
                "To": "+34600111222",
            },
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["accepted"] is True
    assert body["status"] == "delivered"

    events = event_store.list_events(aggregate_id="SM_TEST_123")
    assert len(events) == 1
    assert events[0]["event_type"] == "sms_delivered"


@pytest.mark.asyncio()
async def test_failed_status_with_error_code(
    app_with_event_store: tuple[Any, InMemoryEventStore],
) -> None:
    app, event_store = app_with_event_store
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post(
            "/webhook/twilio-status",
            data={
                "MessageSid": "SM_FAIL_456",
                "MessageStatus": "failed",
                "To": "+34600111222",
                "ErrorCode": "30003",
            },
        )
    assert resp.status_code == 200

    events = event_store.list_events(aggregate_id="SM_FAIL_456")
    assert len(events) == 1
    assert events[0]["event_type"] == "sms_failed"
    assert events[0]["payload"]["error_code"] == "30003"


@pytest.mark.asyncio()
async def test_untracked_status_ignored(
    app_with_event_store: tuple[Any, InMemoryEventStore],
) -> None:
    app, event_store = app_with_event_store
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post(
            "/webhook/twilio-status",
            data={
                "MessageSid": "SM_OTHER",
                "MessageStatus": "accepted",  # not in trackable set
                "To": "+34600111222",
            },
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ignored"] is True


@pytest.mark.asyncio()
async def test_queued_status_event(
    app_with_event_store: tuple[Any, InMemoryEventStore],
) -> None:
    app, event_store = app_with_event_store
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post(
            "/webhook/twilio-status",
            data={
                "MessageSid": "SM_QUEUED_789",
                "MessageStatus": "queued",
                "To": "+34600999888",
            },
        )
    assert resp.status_code == 200

    events = event_store.list_events(aggregate_id="SM_QUEUED_789")
    assert len(events) == 1
    assert events[0]["event_type"] == "sms_queued"


@pytest.mark.asyncio()
async def test_to_number_hashed_in_payload(
    app_with_event_store: tuple[Any, InMemoryEventStore],
) -> None:
    """Phone number must never appear in clear in event payload."""
    app, event_store = app_with_event_store
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        await c.post(
            "/webhook/twilio-status",
            data={
                "MessageSid": "SM_HASH_CHECK",
                "MessageStatus": "sent",
                "To": "+34600111222",
            },
        )

    events = event_store.list_events(aggregate_id="SM_HASH_CHECK")
    payload = events[0]["payload"]
    # to_hash should be a 16-char hex, not the actual phone number
    assert len(payload["to_hash"]) == 16
    assert "+34600111222" not in str(payload)
