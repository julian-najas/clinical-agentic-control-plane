"""Tests for the orchestrator pipeline."""

from __future__ import annotations

import pytest

from cacp.orchestration.orchestrator import Orchestrator
from cacp.settings import Settings
from cacp.storage.event_store import InMemoryEventStore


class TestOrchestrator:
    def setup_method(self) -> None:
        self.settings = Settings(
            hmac_secret="test-secret",
            github_token="",  # no PR creation in tests
            environment="dev",
        )
        self.event_store = InMemoryEventStore()
        self.orchestrator = Orchestrator(
            settings=self.settings,
            event_store=self.event_store,
        )

    @pytest.mark.anyio()
    async def test_full_pipeline(self) -> None:
        result = await self.orchestrator.process_appointment(
            {
                "appointment_id": "APT-E2E-001",
                "patient_id": "PAT-001",
                "clinic_id": "CLINIC-A",
                "scheduled_at": "2026-03-18T10:00:00+00:00",
                "previous_no_shows": 2,
                "is_first_visit": False,
                "patient_phone": "+34600000000",
                "patient_whatsapp": True,
            }
        )
        assert result.proposal_id
        assert result.risk_level in ("low", "medium", "high")
        assert result.risk_score > 0.0
        assert len(result.actions) > 0
        assert result.hmac_signature  # should be signed
        assert result.compliant
        assert result.pr_url is None  # no GitHub token

    @pytest.mark.anyio()
    async def test_events_emitted_in_order(self) -> None:
        await self.orchestrator.process_appointment(
            {
                "appointment_id": "APT-EVT-001",
                "patient_id": "PAT-001",
                "clinic_id": "CLINIC-A",
                "scheduled_at": "2026-03-18T10:00:00+00:00",
                "previous_no_shows": 1,
            }
        )
        events = self.event_store.list_events(aggregate_id="APT-EVT-001")
        # list_events returns newest-first; reverse for chronological
        types = [e["event_type"] for e in reversed(events)]
        assert types == [
            "appointment_received",
            "risk_scored",
            "proposal_created",
            "proposal_signed",
        ]

    @pytest.mark.anyio()
    async def test_unsigned_without_secret(self) -> None:
        settings = Settings(hmac_secret="", github_token="", environment="dev")
        orch = Orchestrator(settings=settings, event_store=InMemoryEventStore())
        result = await orch.process_appointment(
            {
                "appointment_id": "APT-002",
                "patient_id": "PAT-002",
                "clinic_id": "CLINIC-B",
                "scheduled_at": "2026-03-18T10:00:00+00:00",
            }
        )
        assert result.hmac_signature == ""
        assert result.compliant

    @pytest.mark.anyio()
    async def test_high_risk_multiple_actions(self) -> None:
        result = await self.orchestrator.process_appointment(
            {
                "appointment_id": "APT-003",
                "patient_id": "PAT-003",
                "clinic_id": "CLINIC-C",
                "scheduled_at": "2026-03-16T08:00:00+00:00",  # Monday early
                "previous_no_shows": 5,
                "is_first_visit": True,
                "patient_phone": "",
                "patient_whatsapp": False,
            }
        )
        assert result.risk_level == "high"
        assert len(result.actions) >= 3

    @pytest.mark.anyio()
    async def test_actions_have_scheduled_at(self) -> None:
        result = await self.orchestrator.process_appointment(
            {
                "appointment_id": "APT-004",
                "patient_id": "PAT-004",
                "clinic_id": "CLINIC-D",
                "scheduled_at": "2026-03-18T10:00:00+00:00",
                "previous_no_shows": 2,
            }
        )
        for action in result.actions:
            assert "scheduled_at" in action
            assert action["scheduled_at"]  # non-empty
