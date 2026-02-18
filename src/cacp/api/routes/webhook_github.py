"""GitHub webhook endpoint — receives PR merge events."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

from fastapi import APIRouter, Header, Request, status
from pydantic import BaseModel
from starlette.responses import JSONResponse

router = APIRouter()

__all__ = ["router"]

logger = logging.getLogger(__name__)

EXPECTED_REPO = "clinic-gitops-config"
IDEMPOTENCY_TTL = 86400  # 24 h


class WebhookResponse(BaseModel):
    status: str
    message: str


def _verify_signature(payload_body: bytes, secret: str, signature_header: str) -> bool:
    """Verify GitHub HMAC-SHA256 webhook signature."""
    if not signature_header.startswith("sha256="):
        return False
    expected = (
        "sha256="
        + hmac.new(
            secret.encode(),
            payload_body,
            hashlib.sha256,
        ).hexdigest()
    )
    return hmac.compare_digest(expected, signature_header)


@router.post(
    "/webhook/github",
    response_model=WebhookResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Receive GitHub PR merge events",
    operation_id="github_webhook",
)
async def github_webhook(
    request: Request,
    x_github_event: str = Header(default=""),
    x_hub_signature_256: str = Header(default=""),
    x_github_delivery: str = Header(default=""),
) -> JSONResponse:
    """Handle GitHub webhook for PR merged events.

    Flow:
    1. Verify X-Hub-Signature-256
    2. Idempotency via X-GitHub-Delivery in Redis SETNX
    3. Filter: only pull_request / closed / merged
    4. Emit pr_merged event + enqueue actions
    """
    settings = request.app.state.settings
    body = await request.body()

    # ── 1. Signature verification (fail-closed) ────────────────
    if not settings.github_webhook_secret:
        logger.error("GITHUB_WEBHOOK_SECRET not set — rejecting webhook (fail-closed)")
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": "Webhook signature verification not configured"},
        )
    if not _verify_signature(body, settings.github_webhook_secret, x_hub_signature_256):
        return JSONResponse(
            status_code=401,
            content={"status": "error", "message": "Invalid signature"},
        )

    # ── 2. Parse payload ───────────────────────────────────────
    try:
        payload: dict[str, Any] = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Invalid JSON"},
        )

    # ── 3. Idempotency gate ────────────────────────────────────
    redis_client = getattr(request.app.state, "redis_client", None)
    if redis_client and x_github_delivery:
        idem_key = f"cacp:webhook:delivery:{x_github_delivery}"
        was_new = redis_client.set(idem_key, "1", nx=True, ex=IDEMPOTENCY_TTL)
        if not was_new:
            logger.info("Duplicate delivery %s — skipping", x_github_delivery)
            return JSONResponse(
                status_code=200,
                content={"status": "duplicate", "message": "Already processed"},
            )

    # ── 4. Filter: only merged PRs ─────────────────────────────
    if x_github_event != "pull_request":
        return JSONResponse(
            status_code=202,
            content={"status": "ignored", "message": f"Event type '{x_github_event}' ignored"},
        )

    action = payload.get("action", "")
    pr = payload.get("pull_request", {})
    merged = pr.get("merged", False)

    if action != "closed" or not merged:
        return JSONResponse(
            status_code=202,
            content={"status": "ignored", "message": "PR not merged"},
        )

    # ── 5. Validate source repo ────────────────────────────────
    repo_name = payload.get("repository", {}).get("name", "")
    if repo_name != EXPECTED_REPO:
        logger.warning("Webhook from unexpected repo: %s", repo_name)
        return JSONResponse(
            status_code=202,
            content={"status": "ignored", "message": f"Repo '{repo_name}' not tracked"},
        )

    # ── 6. Extract data & emit event ───────────────────────────
    pr_number = pr.get("number", 0)
    merge_sha = pr.get("merge_commit_sha", "")
    pr_title = pr.get("title", "")
    pr_body = pr.get("body", "") or ""

    # Derive appointment_id from PR title or body (convention: "proposal/<id>")
    appointment_id = _extract_appointment_id(pr_title, pr_body)

    event_store = getattr(request.app.state, "event_store", None)
    if event_store:
        event_store.append(
            aggregate_id=appointment_id or f"pr-{pr_number}",
            event_type="pr_merged",
            payload={
                "pr_number": pr_number,
                "merge_commit_sha": merge_sha,
                "appointment_id": appointment_id,
                "repo": repo_name,
            },
        )

    # ── 7. Enqueue job for worker ──────────────────────────────
    if redis_client:
        from cacp.queue.enqueue import enqueue_action

        enqueue_action(
            redis_client,
            {
                "action_type": "execute_plan",
                "pr_number": pr_number,
                "merge_commit_sha": merge_sha,
                "appointment_id": appointment_id,
                "environment": settings.environment,
            },
        )
        logger.info("Enqueued execution for PR #%s (appointment %s)", pr_number, appointment_id)

    return JSONResponse(
        status_code=202,
        content={
            "status": "accepted",
            "message": f"PR #{pr_number} merged — execution enqueued",
        },
    )


def _extract_appointment_id(title: str, body: str) -> str:
    """Best-effort extraction of appointment_id from PR title/body.

    Convention: branch is 'proposal/<uuid-prefix>' and title contains it.
    Body may include 'appointment_id: APT-XXX'.
    """
    # Try body first: "appointment_id: APT-123"
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("appointment_id:"):
            return stripped.split(":", 1)[1].strip()

    # Fallback: extract from title like "proposal/abc123 — APT-100"
    if "—" in title:
        parts = title.split("—")
        if len(parts) > 1:
            return parts[-1].strip()

    return ""
