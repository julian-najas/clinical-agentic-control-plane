"""Health, readiness, and metrics endpoints."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Request, Response
from starlette.responses import JSONResponse

from cacp.healthchecks import check_opa, check_postgres, check_redis

router = APIRouter()

__all__ = ["router"]

# ──────────── In-process metrics counters ────────────
# Replaced by prometheus_client in production; this is a zero-dep baseline.
_metrics: dict[str, Any] = {
    "requests_total": 0,
    "requests_by_status": {},
    "opa_decisions_allow": 0,
    "opa_decisions_deny": 0,
    "opa_errors": 0,
    "queue_depth": 0,
    "start_time": time.time(),
}


def record_request(status: int) -> None:
    """Call from middleware to track request counts."""
    _metrics["requests_total"] += 1
    key = str(status)
    _metrics["requests_by_status"][key] = _metrics["requests_by_status"].get(key, 0) + 1


def record_opa_decision(allowed: bool) -> None:
    if allowed:
        _metrics["opa_decisions_allow"] += 1
    else:
        _metrics["opa_decisions_deny"] += 1


def record_opa_error() -> None:
    _metrics["opa_errors"] += 1


def set_queue_depth(depth: int) -> None:
    _metrics["queue_depth"] = depth


# ──────────── Endpoints ────────────


@router.get("/health", summary="Liveness probe", operation_id="health")
async def health() -> dict[str, str]:
    """Liveness: app process is running."""
    return {"status": "ok"}


@router.get("/ready", summary="Readiness probe", operation_id="ready")
async def ready(request: Request) -> JSONResponse:
    """Readiness: downstream dependencies reachable.

    Returns 200 when all checks pass, 503 otherwise.
    """
    settings = request.app.state.settings
    pg = await check_postgres(settings.pg_dsn)
    rd = await check_redis(settings.redis_url)
    opa = await check_opa(settings.opa_url)

    all_ok = pg and rd and opa
    checks = {"postgres": pg, "redis": rd, "opa": opa}

    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"ready": all_ok, "checks": checks},
    )


@router.get("/metrics", summary="Prometheus metrics", operation_id="metrics")
async def metrics() -> Response:
    """Prometheus text exposition format."""
    uptime = time.time() - _metrics["start_time"]

    lines = [
        "# HELP cacp_up Control plane is up",
        "# TYPE cacp_up gauge",
        "cacp_up 1",
        "",
        "# HELP cacp_uptime_seconds Seconds since process start",
        "# TYPE cacp_uptime_seconds gauge",
        f"cacp_uptime_seconds {uptime:.1f}",
        "",
        "# HELP cacp_requests_total Total HTTP requests",
        "# TYPE cacp_requests_total counter",
        f"cacp_requests_total {_metrics['requests_total']}",
        "",
    ]

    # Per-status breakdown
    for status, count in sorted(_metrics["requests_by_status"].items()):
        lines.append(f'cacp_requests_total{{status="{status}"}} {count}')

    lines += [
        "",
        "# HELP cacp_opa_decisions_total OPA decisions",
        "# TYPE cacp_opa_decisions_total counter",
        f'cacp_opa_decisions_total{{result="allow"}} {_metrics["opa_decisions_allow"]}',
        f'cacp_opa_decisions_total{{result="deny"}} {_metrics["opa_decisions_deny"]}',
        "",
        "# HELP cacp_opa_errors_total OPA unreachable / error count",
        "# TYPE cacp_opa_errors_total counter",
        f"cacp_opa_errors_total {_metrics['opa_errors']}",
        "",
        "# HELP cacp_queue_depth Current items in action queue",
        "# TYPE cacp_queue_depth gauge",
        f"cacp_queue_depth {_metrics['queue_depth']}",
        "",
    ]

    return Response(content="\n".join(lines), media_type="text/plain; charset=utf-8")
