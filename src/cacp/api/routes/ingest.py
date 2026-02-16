"""Appointment ingestion endpoint."""

from __future__ import annotations

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

router = APIRouter()

__all__ = ["router"]


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
    actions_count: int
    pr_url: str | None = None
    message: str


@router.post(
    "/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest an appointment for no-show risk assessment",
    operation_id="ingest_appointment",
)
async def ingest_appointment(appointment: AppointmentIn) -> IngestResponse:
    """Receive an appointment → score risk → generate proposal → open PR."""
    # TODO: wire orchestrator
    return IngestResponse(
        proposal_id="00000000-0000-0000-0000-000000000000",
        risk_level="unknown",
        actions_count=0,
        pr_url=None,
        message="Ingestion endpoint scaffolded — orchestrator not yet wired.",
    )
