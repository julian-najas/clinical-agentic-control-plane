"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from cacp.api.routes import health, ingest, webhook_github

__all__ = ["create_app"]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup: initialise connections (PG, Redis) here
    yield
    # Shutdown: close connections here


def create_app() -> FastAPI:
    app = FastAPI(
        title="Clinical Agentic Control Plane",
        version="0.1.0",
        description="PR-first agentic control plane for clinical no-show reduction.",
        lifespan=lifespan,
    )
    app.include_router(health.router, tags=["health"])
    app.include_router(ingest.router, tags=["ingest"])
    app.include_router(webhook_github.router, tags=["webhook"])
    return app


app = create_app()
