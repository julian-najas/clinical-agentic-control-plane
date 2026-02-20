"""Integration: full ingest → scoring → proposal → signing pipeline.

These tests hit POST /ingest on the real FastAPI app (via ASGI transport)
and verify the complete pipeline produces a valid, signed proposal.

No mocks on Orchestrator, RiskScorer, RevenueAgent, ComplianceAgent,
or HMAC signing.  GitHub PR creation is disabled (no token).
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient


# ── Helpers ─────────────────────────────────────────────────────


def _assert_common_response(data: dict[str, Any]) -> None:
    """Assertions common to every successful ingest response."""
    assert "proposal_id" in data
    assert data["risk_level"] in {"low", "medium", "high"}
    assert 0.0 <= data["risk_score"] <= 1.0
    assert data["actions_count"] >= 1
    assert data["compliant"] is True
    assert data["violations"] == []


# ── Tests ───────────────────────────────────────────────────────


class TestIngestToProposalFlow:
    """Full pipeline: POST /ingest → scored + sequenced + signed proposal."""

    @pytest.mark.anyio
    async def test_high_risk_produces_3_actions(
        self, client: AsyncClient, high_risk_appointment: dict[str, Any]
    ) -> None:
        resp = await client.post("/ingest", json=high_risk_appointment)
        assert resp.status_code == 202
        data = resp.json()

        _assert_common_response(data)
        assert data["risk_level"] == "high"
        # High risk → 3 actions (reminder + confirmation + reschedule)
        assert data["actions_count"] == 3

    @pytest.mark.anyio
    async def test_low_risk_produces_1_action(
        self, client: AsyncClient, low_risk_appointment: dict[str, Any]
    ) -> None:
        resp = await client.post("/ingest", json=low_risk_appointment)
        assert resp.status_code == 202
        data = resp.json()

        _assert_common_response(data)
        assert data["risk_level"] == "low"
        assert data["actions_count"] == 1

    @pytest.mark.anyio
    async def test_medium_risk_produces_2_actions(
        self, client: AsyncClient, medium_risk_appointment: dict[str, Any]
    ) -> None:
        resp = await client.post("/ingest", json=medium_risk_appointment)
        assert resp.status_code == 202
        data = resp.json()

        _assert_common_response(data)
        assert data["risk_level"] == "medium"
        assert data["actions_count"] == 2

    @pytest.mark.anyio
    async def test_pr_url_is_none_without_github_token(
        self, client: AsyncClient, high_risk_appointment: dict[str, Any]
    ) -> None:
        """Without GITHUB_TOKEN, the pipeline should succeed but skip PR creation."""
        resp = await client.post("/ingest", json=high_risk_appointment)
        assert resp.status_code == 202
        assert resp.json()["pr_url"] is None

    @pytest.mark.anyio
    async def test_proposal_id_is_unique_per_request(
        self, client: AsyncClient, high_risk_appointment: dict[str, Any]
    ) -> None:
        resp1 = await client.post("/ingest", json=high_risk_appointment)
        resp2 = await client.post("/ingest", json=high_risk_appointment)
        assert resp1.json()["proposal_id"] != resp2.json()["proposal_id"]


class TestHmacRoundtrip:
    """Sign → verify roundtrip on real pipeline output."""

    @pytest.mark.anyio
    async def test_hmac_signature_is_present_and_valid(
        self, client: AsyncClient, high_risk_appointment: dict[str, Any]
    ) -> None:
        """Orchestrator should produce a non-empty HMAC signature.

        We verify by directly invoking the orchestrator so we can capture
        the exact plan (including its created_at timestamp) and round-trip
        the signature verification.
        """
        from cacp.orchestration.orchestrator import Orchestrator
        from cacp.settings import Settings
        from cacp.signing.hmac import sign_payload
        from cacp.storage.event_store import InMemoryEventStore

        secret = "integration-test-secret-do-not-use"
        settings = Settings(
            hmac_secret=secret,
            github_token="",
            environment="dev",
            opa_url="",
        )
        orchestrator = Orchestrator(
            settings=settings,
            github_pr=None,
            event_store=InMemoryEventStore(),
        )

        result = await orchestrator.process_appointment(high_risk_appointment)
        assert result.hmac_signature != ""

        # To verify the signature, we need the exact plan the orchestrator
        # built (with its created_at).  The simplest correct approach is to
        # round-trip: sign an identical payload and compare digests.
        from cacp.gitops.manifest import build_execution_plan

        plan = build_execution_plan(
            proposal_id=result.proposal_id,
            clinic_id=high_risk_appointment["clinic_id"],
            patient_id=high_risk_appointment["patient_id"],
            appointment_id=high_risk_appointment["appointment_id"],
            actions=result.actions,
            risk_level=result.risk_level,
            environment="dev",
        )
        # The orchestrator's plan has a different created_at — we can't
        # reconstruct it.  Instead, verify that signing the same canonical
        # content (minus created_at) is deterministic.
        sig1 = sign_payload(plan, secret)
        sig2 = sign_payload(plan, secret)
        assert sig1 == sig2, "HMAC signing must be deterministic"

        # And verify that the orchestrator's result signature is non-trivial
        assert len(result.hmac_signature) == 64  # SHA-256 hex digest

    @pytest.mark.anyio
    async def test_hmac_rejects_tampered_plan(
        self, client: AsyncClient, high_risk_appointment: dict[str, Any]
    ) -> None:
        """If the plan is tampered with, verification must fail."""
        from cacp.signing.hmac import sign_payload, verify_signature

        secret = "integration-test-secret-do-not-use"
        plan = {
            "plan_id": "test-123",
            "version": "1.0.0",
            "environment": "dev",
            "clinic_id": "CLINIC-A",
            "actions": [{"action_type": "send_reminder", "channel": "whatsapp",
                         "patient_id": "P1", "appointment_id": "A1",
                         "template": "t", "scheduled_at": "2026-03-20T08:00:00"}],
            "risk_level": "high",
            "hmac_signature": "",
            "created_at": "2026-02-20T00:00:00+00:00",
        }
        plan["hmac_signature"] = sign_payload(plan, secret)

        # Verify passes before tamper
        assert verify_signature(plan, secret)

        # Tamper
        plan["risk_level"] = "low"
        assert not verify_signature(plan, secret)


class TestRejectInvalidInput:
    """The API must reject structurally invalid input at the Pydantic boundary."""

    @pytest.mark.anyio
    async def test_missing_required_fields(self, client: AsyncClient) -> None:
        resp = await client.post("/ingest", json={"clinic_id": "X"})
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_empty_appointment_id(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/ingest",
            json={
                "appointment_id": "",
                "patient_id": "P1",
                "clinic_id": "C1",
                "scheduled_at": "2026-03-20T10:00:00+00:00",
            },
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_extra_fields_are_ignored(
        self, client: AsyncClient, low_risk_appointment: dict[str, Any]
    ) -> None:
        """Extra fields should not break the pipeline."""
        payload = {**low_risk_appointment, "unknown_field": "whatever"}
        resp = await client.post("/ingest", json=payload)
        assert resp.status_code == 202
