"""Tests for compliance agent."""

from __future__ import annotations

from cacp.orchestration.agents.compliance_agent import ComplianceAgent


class TestComplianceAgent:
    def setup_method(self) -> None:
        self.agent = ComplianceAgent()

    def test_under_limit_passes(self) -> None:
        proposal = {
            "actions": [
                {"action_type": "send_reminder", "channel": "sms"},
            ],
        }
        context = {"messages_sent_today": 0, "daily_limit": 5}
        result = self.agent.validate(proposal, context)
        assert result["approved"]

    def test_over_limit_rejected(self) -> None:
        proposal = {
            "actions": [
                {"action_type": "send_reminder", "channel": "sms"},
                {"action_type": "confirm_attendance", "channel": "whatsapp"},
            ],
        }
        context = {"messages_sent_today": 5, "daily_limit": 5}
        result = self.agent.validate(proposal, context)
        assert not result["approved"]
        assert "limit" in result["reason"].lower()

    def test_empty_actions_passes(self) -> None:
        proposal = {"actions": []}
        context = {"messages_sent_today": 0, "daily_limit": 5}
        result = self.agent.validate(proposal, context)
        assert result["approved"]
