"""Appointment ingestion endpoint."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request, status
from pydantic import BaseModel, Field

router = APIRouter()

__all__ = ["router"]

logger = logging.getLogger(__name__)


class AppointmentIn(BaseModel):
    """Incoming appointment data from Clinic Cloud or CSV import."""

    appointment_id: str = Field(min_length=1)
    patient_id: str = Field(min_length=1)
    clinic_id: str = Field(min_length=1)
    scheduled_at: str  # ISO 8601
    treatment_type: str = ""
    is_first_visit: bool = False
    previous_no_shows: int = 0
    patient_phone: str = ""
    patient_whatsapp: bool = False
    consent_given: bool = False


class IngestResponse(BaseModel):
    """Response after ingesting an appointment."""

    proposal_id: str
    risk_level: str
    risk_score: float
    actions_count: int
    pr_url: str | None = None
    compliant: bool = True
    violations: list[str] = []
    message: str


@router.post(
    "/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest an appointment for no-show risk assessment",
    operation_id="ingest_appointment",
)
async def ingest_appointment(
    appointment: AppointmentIn, request: Request
) -> IngestResponse:
    """Receive an appointment → score risk → generate proposal → open PR."""
    orchestrator = request.app.state.orchestrator
    result = await orchestrator.process_appointment(appointment.model_dump())

    return IngestResponse(
        proposal_id=result.proposal_id,
        risk_level=result.risk_level,
        risk_score=result.risk_score,
        actions_count=len(result.actions),
        pr_url=result.pr_url,
        compliant=result.compliant,
        violations=result.violations,
        message=(
            f"Proposal {result.proposal_id[:8]} created "
            f"(risk: {result.risk_level}, score: {result.risk_score:.2f})"
            + (f" — PR: {result.pr_url}" if result.pr_url else "")
        ),
    )
