"""Create PRs in clinic-gitops-config via GitHub API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

__all__ = ["GitHubPRCreator", "PRResult"]


@dataclass(frozen=True)
class PRResult:
    pr_number: int
    pr_url: str
    branch: str


class GitHubPRCreator:
    """Creates HMAC-signed PRs in the gitops-config repository."""

    def __init__(
        self,
        token: str,
        owner: str = "julian-najas",
        repo: str = "clinic-gitops-config",
    ) -> None:
        self._token = token
        self._owner = owner
        self._repo = repo
        self._client = httpx.AsyncClient(
            base_url="https://api.github.com",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
        )

    async def create_plan_pr(
        self,
        plan_manifest: dict[str, Any],
        environment: str,
        branch_name: str,
    ) -> PRResult:
        """Create a branch, commit the plan, and open a PR.

        Args:
            plan_manifest: Signed execution plan.
            environment: Target environment (dev/prod).
            branch_name: Branch name for the PR.

        Returns:
            PRResult with PR number and URL.
        """
        # TODO: implement GitHub API calls
        # 1. Get default branch SHA
        # 2. Create branch
        # 3. Commit plan file to environments/{env}/plans/
        # 4. Create PR with labels ["automated", "hmac-verified"]
        raise NotImplementedError("GitHub PR creation not yet implemented")

    async def close(self) -> None:
        await self._client.aclose()
