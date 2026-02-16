"""Build execution plan manifests for clinic-gitops-config."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

__all__ = ["build_execution_plan"]


def build_execution_plan(
    proposal_id: str,
    clinic_id: str,
    patient_id: str,
    appointment_id: str,
    actions: list[dict[str, Any]],
    risk_level: str,
    environment: str = "dev",
) -> dict[str, Any]:
    """Build an execution plan conforming to execution_plan.schema.json.

    The plan is the artefact committed to clinic-gitops-config.
    Each action embeds patient_id and appointment_id (schema requires them).
    """
    plan_actions: list[dict[str, Any]] = []
    for action in actions:
        plan_actions.append(
            {
                "action_type": action["action_type"],
                "patient_id": patient_id,
                "appointment_id": appointment_id,
                "channel": action["channel"],
                "template": action.get("template", ""),
                "scheduled_at": action.get("scheduled_at", ""),
            }
        )

    return {
        "plan_id": proposal_id,
        "version": "1.0.0",
        "environment": environment,
        "clinic_id": clinic_id,
        "actions": plan_actions,
        "risk_level": risk_level,
        "hmac_signature": "",  # filled after signing
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
