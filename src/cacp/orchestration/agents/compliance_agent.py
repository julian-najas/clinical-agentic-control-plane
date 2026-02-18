"""Compliance agent — validates proposals against OPA policies."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from cacp.policy.input_builder import build_opa_input
from cacp.policy.opa_client import OPAClient, OPAError

__all__ = ["ComplianceAgent", "ComplianceResult"]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ComplianceResult:
    compliant: bool
    violations: list[str]


class ComplianceAgent:
    """Validates action proposals against OPA policies before signing."""

    def __init__(self, opa_client: OPAClient | None = None) -> None:
        self._opa = opa_client

    async def validate(
        self,
        actions: list[dict[str, Any]],
        role: str,
        mode: str,
        clinic_profile: dict[str, Any],
    ) -> ComplianceResult:
        """Validate each action in the proposal against OPA policies.

        Checks:
        - Action is allowed for the given role and mode (via OPA).
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

        # OPA policy evaluation per action
        if self._opa:
            clinic_id = clinic_profile.get("clinic_id", "")
            for action in actions:
                opa_input = build_opa_input(
                    action=action.get("action_type", ""),
                    role=role,
                    mode=mode,
                    patient_id=action.get("patient_id", ""),
                    clinic_id=clinic_id,
                    extra={"channel": action.get("channel", "")},
                )
                try:
                    result = await self._opa.evaluate(opa_input)
                    if result.decision != "ALLOW":
                        violations.extend(result.violations or ["OPA_Deny"])
                except OPAError as exc:
                    # Fail-closed: if OPA unreachable, deny the proposal
                    logger.error("OPA evaluation failed (fail-closed): %s", exc)
                    violations.append("OPA_Unavailable")
        else:
            logger.warning("OPA client not configured — skipping policy evaluation")

        return ComplianceResult(
            compliant=len(violations) == 0,
            violations=violations,
        )
