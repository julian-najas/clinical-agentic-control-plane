"""Twilio SMS adapter — sends real messages when enabled."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

__all__ = ["SendResult", "TwilioSmsAdapter"]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SendResult:
    """Outcome of a send attempt."""

    success: bool
    provider: str
    provider_message_id: str = ""
    error_code: str = ""
    error_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "provider": self.provider,
            "success": self.success,
        }
        if self.provider_message_id:
            d["provider_message_id"] = self.provider_message_id
        if self.error_code:
            d["error_code"] = self.error_code
            d["error_message"] = self.error_message
        return d


class TwilioSmsAdapter:
    """SMS adapter using Twilio REST API.

    Only instantiated when CACP_TWILIO_ENABLED=true and credentials
    are provided. Otherwise the worker falls back to NoopAdapter.
    """

    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        from_number: str,
    ) -> None:
        self._account_sid = account_sid
        self._auth_token = auth_token
        self._from_number = from_number
        # Lazy import — twilio is optional dependency
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            from twilio.rest import Client  # type: ignore[import-untyped,import-not-found]

            self._client = Client(self._account_sid, self._auth_token)
        return self._client

    def execute(self, action: dict[str, Any]) -> dict[str, Any]:
        """Send SMS via Twilio. Conforms to ActionAdapter protocol."""
        to_number = action.get("to_number", "")
        body = action.get("message", "")
        idempotency_key = action.get("idempotency_key", "")

        if not to_number or not body:
            return SendResult(
                success=False,
                provider="twilio",
                error_code="MISSING_PARAMS",
                error_message="to_number and message are required",
            ).to_dict()

        try:
            client = self._get_client()
            message = client.messages.create(
                body=body,
                from_=self._from_number,
                to=to_number,
            )
            logger.info(
                "SMS sent: sid=%s to=%s key=%s",
                message.sid,
                to_number[:6] + "***",
                idempotency_key,
            )
            return SendResult(
                success=True,
                provider="twilio",
                provider_message_id=str(message.sid),
            ).to_dict()
        except Exception as exc:
            error_msg = str(exc)
            logger.error(
                "Twilio send failed: %s (key=%s)",
                error_msg,
                idempotency_key,
            )
            return SendResult(
                success=False,
                provider="twilio",
                error_code="TWILIO_ERROR",
                error_message=error_msg[:200],
            ).to_dict()
