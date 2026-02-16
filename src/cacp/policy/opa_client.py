"""OPA HTTP client with typed errors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

__all__ = ["OPAClient", "OPAResult", "OPAError"]


class OPAError(Exception):
    """Raised when OPA is unreachable or returns an unexpected response."""


@dataclass(frozen=True)
class OPAResult:
    decision: str  # "ALLOW" | "DENY"
    violations: list[str]


class OPAClient:
    """HTTP client for Open Policy Agent evaluation."""

    def __init__(self, base_url: str = "http://localhost:8181") -> None:
        self._base_url = base_url
        self._client = httpx.AsyncClient(base_url=base_url, timeout=5.0)

    async def evaluate(self, input_data: dict[str, Any]) -> OPAResult:
        """Evaluate input against OPA policies.

        Raises OPAError if OPA is unreachable (fail-closed on writes).
        """
        try:
            resp = await self._client.post(
                "/v1/data/clinic/policy",
                json={"input": input_data},
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise OPAError(f"OPA unreachable: {e}") from e

        result = resp.json().get("result", {})
        return OPAResult(
            decision=result.get("decision", "DENY"),
            violations=result.get("violations", []),
        )

    async def close(self) -> None:
        await self._client.aclose()
