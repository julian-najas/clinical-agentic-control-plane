"""Revenue agent — generates action sequences based on risk level.

The revenue agent determines which messages to send and when,
based on the risk score and clinic profile configuration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = ["RevenueAgent", "ActionSequence"]


@dataclass(frozen=True)
class ActionSequence:
    actions: list[dict[str, Any]]
    expected_lift: float  # estimated probability improvement


class RevenueAgent:
    """Generates action sequences optimised for confirmation rates."""

    def generate_sequence(
        self,
        risk_level: str,
        risk_score: float,
        appointment: dict[str, Any],
        clinic_profile: dict[str, Any],
    ) -> ActionSequence:
        """Generate a sequence of messaging actions based on risk level.

        Low risk:    1 reminder (24h before)
        Medium risk: 2 reminders (48h + 24h) + confirmation request
        High risk:   2 reminders + confirmation + reschedule offer (if no reply)
        """
        preferred_channel = clinic_profile.get("messaging", {}).get(
            "preferred_channel", "whatsapp"
        )

        if risk_level == "low":
            actions = [
                {
                    "action_type": "send_reminder",
                    "channel": preferred_channel,
                    "template": "confirm_reminder_v2",
                    "hours_before": 24,
                }
            ]
            expected_lift = 0.05

        elif risk_level == "medium":
            actions = [
                {
                    "action_type": "send_reminder",
                    "channel": preferred_channel,
                    "template": "confirm_reminder_v2",
                    "hours_before": 48,
                },
                {
                    "action_type": "send_confirmation",
                    "channel": preferred_channel,
                    "template": "urgency_short",
                    "hours_before": 24,
                },
            ]
            expected_lift = 0.15

        else:  # high
            actions = [
                {
                    "action_type": "send_reminder",
                    "channel": preferred_channel,
                    "template": "confirm_reminder_v2",
                    "hours_before": 48,
                },
                {
                    "action_type": "send_confirmation",
                    "channel": preferred_channel,
                    "template": "urgency_short",
                    "hours_before": 24,
                },
                {
                    "action_type": "reschedule",
                    "channel": preferred_channel,
                    "template": "reschedule_offer",
                    "hours_before": 2,
                },
            ]
            expected_lift = 0.25

        return ActionSequence(actions=actions, expected_lift=expected_lift)
