"""Shared fixtures for unit tests."""

from __future__ import annotations

from typing import Any

import pytest

from cacp.settings import Settings


@pytest.fixture()
def sample_appointment() -> dict[str, Any]:
    """Appointment payload for testing."""
    return {
        "appointment_id": "APT-100",
        "patient_id": "PAT-001",
        "clinic_id": "CLINIC-A",
        "scheduled_at": "2026-03-15T09:00:00+00:00",
        "treatment_type": "dermatologia",
        "is_first_visit": False,
        "previous_no_shows": 2,
        "patient_phone": "+34600000000",
        "patient_whatsapp": True,
        "consent_given": True,
    }


@pytest.fixture()
def hmac_secret() -> str:
    return "test-secret-key-do-not-use-in-production"


@pytest.fixture()
def test_settings(hmac_secret: str) -> Settings:
    return Settings(
        hmac_secret=hmac_secret,
        github_token="",
        environment="dev",
    )
