"""Build OPA input from proposal context."""

from __future__ import annotations

from typing import Any

__all__ = ["build_opa_input"]


def build_opa_input(
    action: str,
    role: str,
    mode: str,
    patient_id: str,
    clinic_id: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Construct the OPA input document for policy evaluation."""
    input_doc: dict[str, Any] = {
        "action": action,
        "role": role,
        "mode": mode,
        "patient_id": patient_id,
        "clinic_id": clinic_id,
    }
    if extra:
        input_doc.update(extra)
    return input_doc
