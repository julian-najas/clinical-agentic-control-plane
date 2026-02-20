"""Shared fixtures for contract tests.

Contract tests validate that the artefacts produced by this service
conform to the schemas defined in clinic-gitops-config.

The schemas are loaded from a well-known path:
  1. Sibling clone:  ../clinic-gitops-config/specs/
  2. Vendored copy:  specs/vendored/gitops/

This makes CI work whether the gitops-config repo is cloned alongside
(local dev / monorepo) or the schemas are vendored (standalone CI).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

# ── Schema resolution ────────────────────────────────────────────

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SIBLING_GITOPS = _REPO_ROOT.parent / "clinic-gitops-config" / "specs"
_VENDORED_GITOPS = _REPO_ROOT / "specs" / "vendored" / "gitops"
_LOCAL_SPECS = _REPO_ROOT / "specs" / "contracts"


def _load_schema(name: str, search_paths: list[Path]) -> dict[str, Any]:
    for base in search_paths:
        candidate = base / name
        if candidate.is_file():
            return json.loads(candidate.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
    searched = [str(p / name) for p in search_paths]
    msg = f"Schema '{name}' not found in: {searched}"
    raise FileNotFoundError(msg)


# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture()
def gitops_execution_plan_schema() -> dict[str, Any]:
    """The execution_plan schema as defined in clinic-gitops-config."""
    return _load_schema(
        "execution_plan.schema.json",
        [_SIBLING_GITOPS, _VENDORED_GITOPS],
    )


@pytest.fixture()
def gitops_template_schema() -> dict[str, Any]:
    """The template schema as defined in clinic-gitops-config."""
    return _load_schema(
        "template.schema.json",
        [_SIBLING_GITOPS, _VENDORED_GITOPS],
    )


@pytest.fixture()
def local_proposal_schema() -> dict[str, Any]:
    """The proposal schema defined in this repo (cacp)."""
    return _load_schema(
        "proposal.schema.json",
        [_LOCAL_SPECS],
    )
