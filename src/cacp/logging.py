"""Structured logging configuration with trace_id / correlation_id."""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from typing import Any

import structlog

__all__ = [
    "configure_logging",
    "get_logger",
    "correlation_id_var",
    "new_correlation_id",
]

# Context variable for request-scoped correlation
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


def new_correlation_id() -> str:
    """Generate and set a new correlation ID for the current context."""
    cid = str(uuid.uuid4())
    correlation_id_var.set(cid)
    return cid


def _add_correlation_id(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Inject correlation_id into every log entry."""
    cid = correlation_id_var.get("")
    if cid:
        event_dict["correlation_id"] = cid
    return event_dict


def configure_logging(*, json_output: bool = True, level: str = "INFO") -> None:
    """Configure structlog for the application.

    Args:
        json_output: True for JSON (production), False for console (dev).
        level: Log level string.
    """
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        _add_correlation_id,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            structlog.get_level_from_name(level)  # type: ignore[operator]
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(**kwargs: Any) -> structlog.BoundLogger:
    """Get a bound logger with optional initial context."""
    return structlog.get_logger(**kwargs)  # type: ignore[no-any-return]
