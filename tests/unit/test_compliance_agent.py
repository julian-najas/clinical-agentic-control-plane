"""Tests for compliance agent."""

from __future__ import annotations

import pytest

from cacp.orchestration.agents.compliance_agent import ComplianceAgent


class TestComplianceAgent:
    def setup_method(self) -> None:
        self.agent = ComplianceAgent()
        self.clinic_profile = {
            "messaging": {"max_messages_per_patient_per_day": 3},
        }

    @pytest.mark.anyio()
    async def test_under_limit_passes(self) -> None:
        result = await self.agent.validate(
            actions=[{"action_type": "send_reminder", "channel": "sms"}],
            role="agent",
            mode="automated",
            clinic_profile=self.clinic_profile,
        )
        assert result.compliant

    @pytest.mark.anyio()
    async def test_over_limit_rejected(self) -> None:
        actions = [
            {"action_type": f"action_{i}", "channel": "sms"} for i in range(5)
        ]
        result = await self.agent.validate(
            actions=actions,
            role="agent",
            mode="automated",
            clinic_profile=self.clinic_profile,
        )
        assert not result.compliant
        assert len(result.violations) > 0

    @pytest.mark.anyio()
    async def test_empty_actions_passes(self) -> None:
        result = await self.agent.validate(
            actions=[],
            role="agent",
            mode="automated",
            clinic_profile=self.clinic_profile,
        )
        assert result.compliant
