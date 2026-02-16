"""Tests for gitops manifest builder."""

from __future__ import annotations

from cacp.gitops.manifest import build_execution_plan


class TestBuildExecutionPlan:
    def test_contains_required_fields(self) -> None:
        plan = build_execution_plan(
            proposal_id="00000000-0000-0000-0000-000000000001",
            clinic_id="CLINIC-A",
            patient_id="PAT-001",
            appointment_id="APT-100",
            actions=[
                {
                    "action_type": "send_reminder",
                    "channel": "sms",
                    "scheduled_at": "2026-03-14T09:00:00Z",
                }
            ],
            risk_level="low",
        )
        assert plan["plan_id"] == "00000000-0000-0000-0000-000000000001"
        assert plan["clinic_id"] == "CLINIC-A"
        assert plan["version"] == "1.0.0"
        assert plan["environment"] == "dev"
        assert len(plan["actions"]) == 1
        assert "created_at" in plan

    def test_actions_include_patient_id(self) -> None:
        plan = build_execution_plan(
            proposal_id="00000000-0000-0000-0000-000000000002",
            clinic_id="CLINIC-B",
            patient_id="PAT-002",
            appointment_id="APT-200",
            actions=[{"action_type": "send_reminder", "channel": "whatsapp"}],
            risk_level="medium",
        )
        assert plan["actions"][0]["patient_id"] == "PAT-002"

    def test_prod_environment(self) -> None:
        plan = build_execution_plan(
            proposal_id="00000000-0000-0000-0000-000000000003",
            clinic_id="CLINIC-C",
            patient_id="PAT-003",
            appointment_id="APT-300",
            actions=[],
            risk_level="high",
            environment="prod",
        )
        assert plan["environment"] == "prod"
