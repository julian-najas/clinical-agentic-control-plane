"""Build plan manifests for clinic-gitops-config."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

__all__ = ["build_plan_manifest"]


def build_plan_manifest(
    clinic_id: str,
    actions: list[dict[str, Any]],
    risk_level: str,
    environment: str = "dev",
) -> dict[str, Any]:
    """Build an execution plan manifest conforming to execution_plan.schema.json."""
    return {
        "plan_id": str(uuid.uuid4()),
        "version": "0.1.0",
        "environment": environment,
        "clinic_id": clinic_id,
        "actions": actions,
        "risk_level": risk_level,
        "hmac_signature": "",  # to be filled by signing module
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
