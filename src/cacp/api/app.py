"""FastAPI application factory."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from cacp.api.routes import demo, health, ingest, webhook_github, webhook_twilio
from cacp.gitops.github_pr import GitHubPRCreator
from cacp.logging import configure_logging, new_correlation_id
from cacp.orchestration.orchestrator import Orchestrator
from cacp.settings import Settings
from cacp.storage.event_store import InMemoryEventStore

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

__all__ = ["create_app"]

logger = logging.getLogger(__name__)

_ERROR_CODE_BY_STATUS: dict[int, str] = {
    401: "SIGNATURE_INVALID",
    403: "POLICY_VIOLATION",
    429: "RATE_LIMIT_EXCEEDED",
}


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Inject correlation_id and record request metrics."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        cid = request.headers.get("x-correlation-id") or new_correlation_id()
        request.state.request_id = cid

        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        response.headers["x-correlation-id"] = cid
        response.headers["x-request-duration-ms"] = f"{duration * 1000:.1f}"

        # Record metrics
        health.record_request(response.status_code)

        return response


def _resolve_request_id(request: Request) -> str:
    state_request_id = getattr(request.state, "request_id", "")
    if state_request_id:
        return state_request_id
    header_request_id = request.headers.get("x-correlation-id", "")
    if header_request_id:
        request.state.request_id = header_request_id
        return header_request_id
    generated = new_correlation_id()
    request.state.request_id = generated
    return generated


def _error_payload(error_code: str, message: str, request_id: str, *, details: Any = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "error_code": error_code,
        "message": message,
        "request_id": request_id,
    }
    if details is not None:
        payload["details"] = details
    return payload


async def _http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    request_id = _resolve_request_id(request)
    status_code = exc.status_code

    if status_code in _ERROR_CODE_BY_STATUS:
        error_code = _ERROR_CODE_BY_STATUS[status_code]
    elif 400 <= status_code < 500:
        error_code = "INVALID_REQUEST"
    else:
        error_code = "INTERNAL_ERROR"

    if isinstance(exc.detail, str):
        message = exc.detail
    else:
        message = "Request failed"

    return JSONResponse(
        status_code=status_code,
        content=_error_payload(error_code, message, request_id),
    )


async def _validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    request_id = _resolve_request_id(request)
    return JSONResponse(
        status_code=422,
        content=_error_payload(
            "INVALID_REQUEST",
            "Request validation failed",
            request_id,
            details=exc.errors(),
        ),
    )


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = _resolve_request_id(request)
    logger.exception("Unhandled application exception", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content=_error_payload("INTERNAL_ERROR", "Internal server error", request_id),
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup
    configure_logging(json_output=True, level="INFO")
    settings = Settings()

    # Build GitHub PR creator (if token available)
    github_pr: GitHubPRCreator | None = None
    if settings.github_token:
        github_pr = GitHubPRCreator(
            token=settings.github_token,
            owner=settings.github_owner,
            repo=settings.github_repo,
        )

    # Build event store (in-memory default; PG wired separately if pg_dsn set)
    event_store = InMemoryEventStore()

    # Initialize Redis client (needed for webhook idempotency + enqueue)
    redis_client = None
    if settings.redis_url:
        from cacp.queue.redis import get_redis_client

        redis_client = get_redis_client(settings.redis_url)

    # Build orchestrator with all dependencies
    app.state.orchestrator = Orchestrator(
        settings=settings,
        github_pr=github_pr,
        event_store=event_store,
    )
    app.state.settings = settings
    app.state.event_store = event_store
    app.state.redis_client = redis_client

    yield

    # Shutdown: close Redis
    if redis_client:
        redis_client.close()

    # Shutdown
    if github_pr:
        await github_pr.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Clinical Agentic Control Plane",
        version="0.1.0",
        description="PR-first agentic control plane for clinical no-show reduction.",
        lifespan=lifespan,
    )
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)
    app.add_middleware(ObservabilityMiddleware)
    app.include_router(health.router, tags=["health"])
    app.include_router(ingest.router, tags=["ingest"])
    app.include_router(webhook_github.router, tags=["webhook"])
    app.include_router(webhook_twilio.router, tags=["webhook"])
    app.include_router(demo.router, tags=["demo"])
    return app


app = create_app()
