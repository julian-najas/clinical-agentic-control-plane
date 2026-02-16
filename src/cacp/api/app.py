"""FastAPI application factory."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from cacp.api.routes import health, ingest, webhook_github
from cacp.logging import configure_logging, new_correlation_id

__all__ = ["create_app"]


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Inject correlation_id and record request metrics."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        cid = request.headers.get("x-correlation-id") or new_correlation_id()

        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        response.headers["x-correlation-id"] = cid
        response.headers["x-request-duration-ms"] = f"{duration * 1000:.1f}"

        # Record metrics
        health.record_request(response.status_code)

        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup
    configure_logging(json_output=True, level="INFO")
    yield
    # Shutdown: close connections here


def create_app() -> FastAPI:
    app = FastAPI(
        title="Clinical Agentic Control Plane",
        version="0.1.0",
        description="PR-first agentic control plane for clinical no-show reduction.",
        lifespan=lifespan,
    )
    app.add_middleware(ObservabilityMiddleware)
    app.include_router(health.router, tags=["health"])
    app.include_router(ingest.router, tags=["ingest"])
    app.include_router(webhook_github.router, tags=["webhook"])
    return app


app = create_app()
