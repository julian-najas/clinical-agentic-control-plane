"""GitHub webhook endpoint — receives PR merge events."""

from __future__ import annotations

from fastapi import APIRouter, Header, Request, status
from pydantic import BaseModel

router = APIRouter()

__all__ = ["router"]


class WebhookResponse(BaseModel):
    status: str
    message: str


@router.post(
    "/webhook/github",
    response_model=WebhookResponse,
    status_code=status.HTTP_200_OK,
    summary="Receive GitHub PR merge events",
    operation_id="github_webhook",
)
async def github_webhook(
    request: Request,
    x_github_event: str = Header(default=""),
    x_hub_signature_256: str = Header(default=""),
) -> WebhookResponse:
    """Handle GitHub webhook for PR merged events.

    When a proposal PR is merged in clinic-gitops-config,
    this endpoint triggers action execution via the worker queue.
    """
    # TODO: verify webhook signature, parse event, enqueue actions
    _ = await request.json()
    return WebhookResponse(
        status="received",
        message="Webhook endpoint scaffolded — worker not yet wired.",
    )
