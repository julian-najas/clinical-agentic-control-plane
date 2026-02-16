"""Orchestrator — coordinates scoring, sequencing, and governance."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = ["Orchestrator", "OrchestratorResult"]


@dataclass(frozen=True)
class OrchestratorResult:
    proposal_id: str
    risk_level: str
    risk_score: float
    actions: list[dict[str, Any]]
    hmac_signature: str
    pr_url: str | None


class Orchestrator:
    """Coordinates the full pipeline: score → sequence → validate → sign → PR."""

    async def process_appointment(self, appointment: dict[str, Any]) -> OrchestratorResult:
        """Process a single appointment through the full pipeline.

        Steps:
        1. Calculate risk score (risk_scorer)
        2. Generate action sequence (revenue_agent)
        3. Validate against policies (compliance_agent)
        4. Sign proposal with HMAC
        5. Open PR in clinic-gitops-config

        Returns:
            OrchestratorResult with proposal details and PR URL.
        """
        # TODO: implement pipeline
        return OrchestratorResult(
            proposal_id="00000000-0000-0000-0000-000000000000",
            risk_level="unknown",
            risk_score=0.0,
            actions=[],
            hmac_signature="",
            pr_url=None,
        )
