"""Orchestrator — real pipeline: score → sequence → validate → sign → PR."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cacp.gitops.github_pr import GitHubPRCreator
    from cacp.settings import Settings
    from cacp.storage.event_store import EventStoreProtocol

from cacp.gitops.manifest import build_execution_plan
from cacp.orchestration.agents.compliance_agent import ComplianceAgent
from cacp.orchestration.agents.revenue_agent import RevenueAgent
from cacp.scoring.risk_scorer import RiskScorer
from cacp.signing.hmac import sign_payload

__all__ = ["Orchestrator", "OrchestratorResult"]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OrchestratorResult:
    proposal_id: str
    risk_level: str
    risk_score: float
    actions: list[dict[str, Any]]
    hmac_signature: str
    pr_url: str | None
    compliant: bool = True
    violations: list[str] = field(default_factory=list)


class Orchestrator:
    """Coordinates the full pipeline: score → sequence → validate → sign → PR."""

    def __init__(
        self,
        settings: Settings,
        github_pr: GitHubPRCreator | None = None,
        event_store: EventStoreProtocol | None = None,
    ) -> None:
        self._settings = settings
        self._scorer = RiskScorer()
        self._revenue = RevenueAgent()
        self._compliance = ComplianceAgent()
        self._github_pr = github_pr
        self._events = event_store

    def _emit(self, aggregate_id: str, event_type: str, payload: dict[str, Any]) -> None:
        """Fire-and-forget event append (swallows errors in prod)."""
        if self._events is None:
            return
        try:
            self._events.append(
                aggregate_id=aggregate_id,
                event_type=event_type,
                payload=payload,
            )
        except Exception:
            logger.warning("Event store append failed for %s", event_type, exc_info=True)

    async def process_appointment(
        self,
        appointment: dict[str, Any],
    ) -> OrchestratorResult:
        """Process a single appointment through the full pipeline.

        Steps:
        1. Calculate risk score
        2. Generate action sequence
        3. Validate compliance
        4. Build execution plan
        5. Sign with HMAC
        6. Open PR in clinic-gitops-config
        """
        proposal_id = str(uuid.uuid4())
        appt_id = appointment.get("appointment_id", proposal_id)

        # ── Event: appointment_received ────────────────────────────
        self._emit(appt_id, "appointment_received", appointment)

        # 1 ── Risk scoring ─────────────────────────────────────────
        risk = self._scorer.score(appointment)
        logger.info(
            "Risk scored: %s (%.4f) for %s",
            risk.level,
            risk.score,
            appt_id,
        )
        self._emit(appt_id, "risk_scored", {"score": risk.score, "level": risk.level})

        # 2 ── Action sequence ──────────────────────────────────────
        clinic_profile = {
            "messaging": {
                "preferred_channel": "whatsapp",
                "max_messages_per_patient_per_day": 3,
            },
        }
        sequence = self._revenue.generate_sequence(
            risk_level=risk.level,
            risk_score=risk.score,
            appointment=appointment,
            clinic_profile=clinic_profile,
        )

        # Resolve hours_before → absolute scheduled_at
        scheduled_at = appointment.get("scheduled_at", "")
        resolved_actions = _resolve_scheduled_times(sequence.actions, scheduled_at)

        # 3 ── Compliance check ─────────────────────────────────────
        compliance = await self._compliance.validate(
            actions=resolved_actions,
            role="agent",
            mode="automated",
            clinic_profile=clinic_profile,
        )
        if not compliance.compliant:
            logger.warning(
                "Compliance rejected proposal %s: %s",
                proposal_id,
                compliance.violations,
            )
            return OrchestratorResult(
                proposal_id=proposal_id,
                risk_level=risk.level,
                risk_score=risk.score,
                actions=resolved_actions,
                hmac_signature="",
                pr_url=None,
                compliant=False,
                violations=compliance.violations,
            )

        # 4 ── Build execution plan ─────────────────────────────────
        plan = build_execution_plan(
            proposal_id=proposal_id,
            clinic_id=appointment.get("clinic_id", ""),
            patient_id=appointment.get("patient_id", ""),
            appointment_id=appointment.get("appointment_id", ""),
            actions=resolved_actions,
            risk_level=risk.level,
            environment=self._settings.environment,
        )

        # ── Event: proposal_created ─────────────────────────────
        self._emit(
            appt_id,
            "proposal_created",
            {"proposal_id": proposal_id, "actions": len(resolved_actions)},
        )

        # 5 ── HMAC sign ───────────────────────────────────────────
        if not self._settings.hmac_secret:
            logger.warning("HMAC_SECRET not set — plan will be unsigned")
            signature = ""
        else:
            signature = sign_payload(plan, self._settings.hmac_secret)
        plan["hmac_signature"] = signature
        self._emit(
            appt_id,
            "proposal_signed",
            {"proposal_id": proposal_id, "signed": bool(signature)},
        )

        # 6 ── Open PR ─────────────────────────────────────────────
        pr_url: str | None = None
        if self._github_pr and self._settings.github_token:
            try:
                pr_result = await self._github_pr.create_plan_pr(
                    plan_manifest=plan,
                    environment=self._settings.environment,
                    branch_name=f"proposal/{proposal_id[:8]}",
                )
                pr_url = pr_result.pr_url
                logger.info("PR created: %s", pr_url)
                self._emit(appt_id, "pr_opened", {"proposal_id": proposal_id, "pr_url": pr_url})
            except Exception:
                logger.exception("Failed to create PR for proposal %s", proposal_id)
        else:
            logger.info("GitHub PR creation skipped (no token configured)")

        return OrchestratorResult(
            proposal_id=proposal_id,
            risk_level=risk.level,
            risk_score=risk.score,
            actions=resolved_actions,
            hmac_signature=signature,
            pr_url=pr_url,
            compliant=True,
            violations=[],
        )


def _resolve_scheduled_times(
    actions: list[dict[str, Any]],
    appointment_iso: str,
) -> list[dict[str, Any]]:
    """Convert hours_before to absolute scheduled_at."""
    try:
        appt_dt = datetime.fromisoformat(appointment_iso)
    except (ValueError, TypeError):
        appt_dt = datetime.now(UTC) + timedelta(days=1)

    resolved: list[dict[str, Any]] = []
    for action in actions:
        a = dict(action)  # shallow copy
        hours = a.pop("hours_before", None)
        if hours is not None and "scheduled_at" not in a:
            scheduled = appt_dt - timedelta(hours=int(hours))
            a["scheduled_at"] = scheduled.isoformat()
        resolved.append(a)
    return resolved
