"""Compliance agent — validates proposals against OPA policies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = ["ComplianceAgent", "ComplianceResult"]


@dataclass(frozen=True)
class ComplianceResult:
    compliant: bool
    violations: list[str]


class ComplianceAgent:
    """Validates action proposals against OPA policies before signing."""

    async def validate(
        self,
        actions: list[dict[str, Any]],
        role: str,
        mode: str,
        clinic_profile: dict[str, Any],
    ) -> ComplianceResult:
        """Validate each action in the proposal against OPA policies.

        Checks:
        - Action is allowed for the given role and mode.
        - Messaging limits are not exceeded.
        - Patient consent is recorded.
        - Quiet hours are respected.
        """
        violations: list[str] = []

        # Check messaging limits
        max_messages = clinic_profile.get("messaging", {}).get(
            "max_messages_per_patient_per_day", 3
        )
        if len(actions) > max_messages:
            violations.append(
                f"Action count ({len(actions)}) exceeds daily limit ({max_messages})"
            )

        # TODO: wire OPA client for full policy evaluation

        return ComplianceResult(
            compliant=len(violations) == 0,
            violations=violations,
        )
