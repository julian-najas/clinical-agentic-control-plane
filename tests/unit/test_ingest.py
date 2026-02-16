"""Tests for the /ingest endpoint."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from cacp.api.app import create_app
from cacp.orchestration.orchestrator import Orchestrator
from cacp.settings import Settings


def _app_with_orchestrator():  # type: ignore[no-untyped-def]
    """Create app with orchestrator wired (lifespan doesn't fire in ASGITransport)."""
    app = create_app()
    settings = Settings(hmac_secret="test-secret", github_token="", environment="dev")
    app.state.orchestrator = Orchestrator(settings=settings)
    app.state.settings = settings
    return app


@pytest.mark.anyio()
async def test_ingest_returns_proposal() -> None:
    app = _app_with_orchestrator()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/ingest",
            json={
                "appointment_id": "APT-TEST-001",
                "patient_id": "PAT-001",
                "clinic_id": "CLINIC-A",
                "scheduled_at": "2026-03-18T10:00:00+00:00",
                "previous_no_shows": 1,
                "patient_phone": "+34600000000",
                "patient_whatsapp": True,
                "consent_given": True,
            },
        )
    assert resp.status_code == 202
    data = resp.json()
    assert data["proposal_id"]
    assert data["risk_level"] in ("low", "medium", "high")
    assert data["risk_score"] > 0.0
    assert data["actions_count"] >= 1
    assert data["compliant"] is True


@pytest.mark.anyio()
async def test_ingest_missing_fields_fails() -> None:
    app = _app_with_orchestrator()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/ingest", json={"appointment_id": "X"})
    assert resp.status_code == 422  # validation error


@pytest.mark.anyio()
async def test_ingest_high_risk_patient() -> None:
    app = _app_with_orchestrator()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/ingest",
            json={
                "appointment_id": "APT-HIGH-001",
                "patient_id": "PAT-HIGH",
                "clinic_id": "CLINIC-A",
                "scheduled_at": "2026-03-16T08:00:00+00:00",
                "previous_no_shows": 4,
                "is_first_visit": True,
                "patient_phone": "",
                "patient_whatsapp": False,
            },
        )
    assert resp.status_code == 202
    data = resp.json()
    assert data["risk_level"] == "high"
    assert data["actions_count"] >= 3
