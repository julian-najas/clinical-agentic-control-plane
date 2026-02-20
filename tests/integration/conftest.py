"""Shared fixtures for integration tests.

These tests exercise the real pipeline end-to-end:
    ingest → scoring → sequencing → compliance → signing → plan build

No mocks on internal components.  External boundaries (GitHub API, OPA)
are replaced with explicit test doubles to keep CI deterministic.
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from cacp.api.app import create_app
from cacp.settings import Settings
from cacp.storage.event_store import InMemoryEventStore


# ── Deterministic settings (no external deps) ────────────────────


@pytest.fixture()
def integration_settings() -> Settings:
    """Settings that enable HMAC signing but disable GitHub PR creation."""
    return Settings(
        hmac_secret="integration-test-secret-do-not-use",
        github_token="",  # PR creation disabled
        environment="dev",
        opa_url="",  # OPA disabled — compliance falls through to local checks
    )


@pytest.fixture()
def event_store() -> InMemoryEventStore:
    return InMemoryEventStore()


@pytest.fixture()
async def client() -> AsyncClient:  # type: ignore[misc]
    """Full ASGI client against the real FastAPI app.

    The app is created with default settings (from env / defaults).
    HMAC_SECRET must be set via env or the signature tests will be empty.
    """
    import os

    os.environ.setdefault("CACP_HMAC_SECRET", "integration-test-secret-do-not-use")
    os.environ.setdefault("CACP_GITHUB_TOKEN", "")
    os.environ.setdefault("CACP_OPA_URL", "")

    app = create_app()
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac  # type: ignore[misc]


# ── Canonical appointment fixtures ───────────────────────────────


@pytest.fixture()
def high_risk_appointment() -> dict[str, Any]:
    """Appointment that will score as HIGH risk."""
    return {
        "appointment_id": "INT-APT-001",
        "patient_id": "INT-PAT-001",
        "clinic_id": "INT-CLINIC-A",
        "scheduled_at": "2026-03-20T08:00:00+00:00",
        "treatment_type": "dermatologia",
        "is_first_visit": True,
        "previous_no_shows": 3,
        "patient_phone": "+34600000001",
        "patient_whatsapp": True,
        "consent_given": True,
    }


@pytest.fixture()
def low_risk_appointment() -> dict[str, Any]:
    """Appointment that will score as LOW risk."""
    return {
        "appointment_id": "INT-APT-002",
        "patient_id": "INT-PAT-002",
        "clinic_id": "INT-CLINIC-A",
        "scheduled_at": "2026-03-20T10:00:00+00:00",
        "treatment_type": "limpieza",
        "is_first_visit": False,
        "previous_no_shows": 0,
        "patient_phone": "+34600000002",
        "patient_whatsapp": True,
        "consent_given": True,
    }


@pytest.fixture()
def medium_risk_appointment() -> dict[str, Any]:
    """Appointment that will score as MEDIUM risk."""
    return {
        "appointment_id": "INT-APT-003",
        "patient_id": "INT-PAT-003",
        "clinic_id": "INT-CLINIC-A",
        "scheduled_at": "2026-03-20T10:00:00+00:00",
        "treatment_type": "ortodoncia",
        "is_first_visit": True,
        "previous_no_shows": 1,
        "patient_phone": "+34600000003",
        "patient_whatsapp": True,
        "consent_given": True,
    }
