"""Demo / ROI simulation endpoints.

``GET /demo/dental-roi``  — JSON projection
``GET /demo/dental-roi/csv`` — downloadable CSV with per-appointment detail
"""

from __future__ import annotations

import csv
import io
from typing import Any

from fastapi import APIRouter, Query
from starlette.responses import JSONResponse, StreamingResponse

from cacp.demo.roi_projection import project_roi
from cacp.demo.simulator import generate_cohort

router = APIRouter()

__all__ = ["router"]


@router.get(
    "/demo/dental-roi",
    summary="Dental clinic ROI simulation",
    operation_id="demo_dental_roi",
)
async def dental_roi(
    citas: int = Query(800, ge=10, le=10000, description="Monthly appointments"),
    no_show: float = Query(0.12, ge=0.01, le=0.50, description="Baseline no-show rate"),
    ticket: float = Query(
        90.0,
        ge=10,
        le=1000,
        description="Avg ticket EUR (ignored — computed from sim)",
    ),
    reduction: float = Query(0.35, ge=0.05, le=0.80, description="SMS reduction of no-shows"),
    sms_cost: float = Query(0.07, ge=0.01, le=1.0, description="SMS cost per message EUR"),
    seed: int = Query(42, description="Random seed for reproducibility"),
) -> JSONResponse:
    """Run a simulated month of dental appointments and project ROI.

    Default parameters match a realistic Spanish private dental clinic:
    800 citas, 12% no-show, 35% reduction via SMS.
    """
    sim = generate_cohort(
        num_appointments=citas,
        baseline_noshow_rate=no_show,
        sms_reduction_rate=reduction,
        seed=seed,
    )
    roi = project_roi(sim, sms_cost_per_message=sms_cost)

    return JSONResponse(
        status_code=200,
        content={
            **roi.to_dict(),
            "executive_summary": roi.to_executive_summary(),
            "simulation": sim.to_dict(),
        },
    )


@router.get(
    "/demo/dental-roi/csv",
    summary="Download appointment-level CSV",
    operation_id="demo_dental_roi_csv",
)
async def dental_roi_csv(
    citas: int = Query(800, ge=10, le=10000),
    no_show: float = Query(0.12, ge=0.01, le=0.50),
    reduction: float = Query(0.35, ge=0.05, le=0.80),
    seed: int = Query(42),
) -> StreamingResponse:
    """Generate a CSV file with per-appointment detail for analysis."""
    sim = generate_cohort(
        num_appointments=citas,
        baseline_noshow_rate=no_show,
        sms_reduction_rate=reduction,
        seed=seed,
    )

    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=[
            "appointment_id",
            "patient_id",
            "type",
            "scheduled_at",
            "ticket_eur",
            "noshow_baseline",
            "sms_sent",
            "sms_confirmed",
            "noshow_after_sms",
        ],
    )
    writer.writeheader()
    rows: list[dict[str, Any]] = [a.to_dict() for a in sim.appointments]
    writer.writerows(rows)

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=clinic_simulation_{citas}citas.csv",
        },
    )
