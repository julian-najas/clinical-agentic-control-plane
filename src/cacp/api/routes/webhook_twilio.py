"""Twilio delivery-status webhook: converts status callbacks into events."""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, Request
from starlette.responses import JSONResponse

if TYPE_CHECKING:
    from cacp.storage.event_store import EventStoreProtocol

__all__ = ["router"]

logger = logging.getLogger(__name__)
router = APIRouter()

# Twilio status progression
_TERMINAL_STATUSES = frozenset({"delivered", "undelivered", "failed"})
_TRACKABLE_STATUSES = frozenset({"queued", "sent", "delivered", "undelivered", "failed"})


def _verify_twilio_signature(
    url: str,
    params: dict[str, str],
    signature: str,
    auth_token: str,
) -> bool:
    """Validate Twilio X-Twilio-Signature header.

    Twilio signs: URL + sorted POST params concatenated, HMAC-SHA1.
    """
    if not auth_token or not signature:
        return False
    data = url
    for key in sorted(params.keys()):
        data += key + params[key]

    expected = hmac.new(auth_token.encode("utf-8"), data.encode("utf-8"), hashlib.sha1).digest()

    import base64

    expected_b64 = base64.b64encode(expected).decode("utf-8")
    return hmac.compare_digest(expected_b64, signature)


def _emit_event(
    event_store: EventStoreProtocol | None,
    aggregate_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    """Fire-and-forget event emit."""
    if event_store is None:
        return
    try:
        event_store.append(
            aggregate_id=aggregate_id,
            event_type=event_type,
            payload=payload,
        )
    except Exception:
        logger.warning("Event store append failed for %s", event_type, exc_info=True)


@router.post(
    "/webhook/twilio-status",
    summary="Twilio delivery status callback",
    operation_id="twilio_status_callback",
)
async def twilio_status_callback(request: Request) -> JSONResponse:
    """Receive Twilio message status updates.

    Expected POST params: MessageSid, MessageStatus, To, ErrorCode (optional).
    """
    settings = request.app.state.settings

    # Parse form body (Twilio sends application/x-www-form-urlencoded)
    form = await request.form()
    params: dict[str, str] = {k: str(v) for k, v in form.items()}

    # Signature verification (skip if no auth token configured)
    if settings.twilio_auth_token:
        sig = request.headers.get("X-Twilio-Signature", "")
        url = str(request.url)
        if not _verify_twilio_signature(url, params, sig, settings.twilio_auth_token):
            logger.warning("Twilio signature verification failed")
            raise HTTPException(status_code=401, detail="Invalid signature")

    message_sid = params.get("MessageSid", "")
    status = params.get("MessageStatus", "")
    to_number = params.get("To", "")
    error_code = params.get("ErrorCode")

    if not message_sid or status not in _TRACKABLE_STATUSES:
        return JSONResponse(
            status_code=200,
            content={"ignored": True, "reason": "untracked_status"},
        )

    # Build event
    event_type = f"sms_{status}"
    payload: dict[str, Any] = {
        "message_sid": message_sid,
        "status": status,
        "to_hash": hashlib.sha256(to_number.encode("utf-8")).hexdigest()[:16],
    }
    if error_code:
        payload["error_code"] = error_code

    # Use message_sid as aggregate (we don't have appointment_id here)
    event_store: EventStoreProtocol | None = getattr(request.app.state, "event_store", None)
    _emit_event(event_store, message_sid, event_type, payload)

    logger.info("Twilio status: sid=%s status=%s", message_sid[:10] + "...", status)

    return JSONResponse(status_code=200, content={"accepted": True, "status": status})
