"""Tests for revenue agent."""

from __future__ import annotations

from cacp.orchestration.agents.revenue_agent import RevenueAgent


class TestRevenueAgent:
    def setup_method(self) -> None:
        self.agent = RevenueAgent()

    def test_low_risk_single_reminder(self) -> None:
        actions = self.agent.generate_actions(risk_score=0.2, no_show_history=0)
        assert len(actions) == 1
        assert actions[0]["action_type"] == "send_reminder"

    def test_medium_risk_two_plus_confirm(self) -> None:
        actions = self.agent.generate_actions(risk_score=0.5, no_show_history=1)
        types = [a["action_type"] for a in actions]
        assert "send_reminder" in types
        assert "confirm_attendance" in types
        assert len(actions) >= 2

    def test_high_risk_full_sequence(self) -> None:
        actions = self.agent.generate_actions(risk_score=0.8, no_show_history=3)
        types = [a["action_type"] for a in actions]
        assert "send_reminder" in types
        assert "confirm_attendance" in types
        assert "offer_reschedule" in types
        assert len(actions) >= 3

    def test_actions_have_expected_lift(self) -> None:
        actions = self.agent.generate_actions(risk_score=0.6, no_show_history=2)
        for action in actions:
            assert "expected_lift" in action
            assert isinstance(action["expected_lift"], float)
            assert 0.0 < action["expected_lift"] <= 1.0
