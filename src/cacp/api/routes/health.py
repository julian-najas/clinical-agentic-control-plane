"""Health and metrics endpoints."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()

__all__ = ["router"]


@router.get("/health", summary="Liveness probe", operation_id="health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/metrics", summary="Prometheus metrics", operation_id="metrics")
async def metrics() -> str:
    """Prometheus text exposition format."""
    # TODO: wire real metrics
    return "# HELP cacp_up Control plane is up\n# TYPE cacp_up gauge\ncacp_up 1\n"
