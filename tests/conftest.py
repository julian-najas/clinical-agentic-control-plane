"""Shared fixtures for unit tests."""

from __future__ import annotations

import pytest


@pytest.fixture()
def sample_appointment() -> dict[str, object]:
    """Minimal appointment payload for testing."""
    return {
        "patient_id": "PAT-001",
        "appointment_id": "APT-100",
        "clinic_id": "CLINIC-A",
        "datetime": "2026-03-15T09:00:00Z",
        "specialty": "dermatologia",
        "no_show_history": 2,
        "risk_score": 0.72,
    }


@pytest.fixture()
def hmac_secret() -> str:
    return "test-secret-key-do-not-use-in-production"
