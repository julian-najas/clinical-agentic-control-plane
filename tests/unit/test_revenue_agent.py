"""Tests for revenue agent."""

from __future__ import annotations

from cacp.orchestration.agents.revenue_agent import RevenueAgent


class TestRevenueAgent:
    def setup_method(self) -> None:
        self.agent = RevenueAgent()
        self.clinic_profile = {
            "messaging": {
                "preferred_channel": "whatsapp",
                "max_messages_per_patient_per_day": 3,
            },
        }
        self.appointment = {
            "appointment_id": "APT-100",
            "scheduled_at": "2026-03-15T09:00:00+00:00",
        }

    def test_low_risk_single_reminder(self) -> None:
        seq = self.agent.generate_sequence(
            risk_level="low",
            risk_score=0.2,
            appointment=self.appointment,
            clinic_profile=self.clinic_profile,
        )
        assert len(seq.actions) == 1
        assert seq.actions[0]["action_type"] == "send_reminder"

    def test_medium_risk_two_actions(self) -> None:
        seq = self.agent.generate_sequence(
            risk_level="medium",
            risk_score=0.5,
            appointment=self.appointment,
            clinic_profile=self.clinic_profile,
        )
        types = [a["action_type"] for a in seq.actions]
        assert "send_reminder" in types
        assert "send_confirmation" in types
        assert len(seq.actions) >= 2

    def test_high_risk_full_sequence(self) -> None:
        seq = self.agent.generate_sequence(
            risk_level="high",
            risk_score=0.8,
            appointment=self.appointment,
            clinic_profile=self.clinic_profile,
        )
        types = [a["action_type"] for a in seq.actions]
        assert "send_reminder" in types
        assert "reschedule" in types
        assert len(seq.actions) >= 3

    def test_expected_lift_positive(self) -> None:
        seq = self.agent.generate_sequence(
            risk_level="medium",
            risk_score=0.5,
            appointment=self.appointment,
            clinic_profile=self.clinic_profile,
        )
        assert seq.expected_lift > 0.0

    def test_preferred_channel_used(self) -> None:
        profile = {
            "messaging": {
                "preferred_channel": "sms",
                "max_messages_per_patient_per_day": 3,
            },
        }
        seq = self.agent.generate_sequence(
            risk_level="low",
            risk_score=0.1,
            appointment=self.appointment,
            clinic_profile=profile,
        )
        assert seq.actions[0]["channel"] == "sms"
