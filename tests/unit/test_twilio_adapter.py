"""Tests for Twilio SMS adapter (unit-level, mocked client)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from cacp.adapters.twilio_sms import SendResult, TwilioSmsAdapter


class TestSendResult:
    def test_to_dict_success(self) -> None:
        sr = SendResult(
            success=True,
            provider="twilio",
            provider_message_id="SM123",
        )
        d = sr.to_dict()
        assert d["success"] is True
        assert d["provider_message_id"] == "SM123"
        assert "error_code" not in d

    def test_to_dict_failure(self) -> None:
        sr = SendResult(
            success=False,
            provider="twilio",
            error_code="21211",
            error_message="Invalid phone",
        )
        d = sr.to_dict()
        assert d["success"] is False
        assert d["error_code"] == "21211"


class TestTwilioSmsAdapter:
    def setup_method(self) -> None:
        self.adapter = TwilioSmsAdapter(
            account_sid="ACtest",
            auth_token="token-test",
            from_number="+15005550006",
        )

    def test_execute_success(self) -> None:
        mock_message = MagicMock()
        mock_message.sid = "SM_MOCK_123"
        mock_message.status = "queued"

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message

        with patch.object(self.adapter, "_get_client", return_value=mock_client):
            action: dict[str, Any] = {
                "action_type": "execute_plan",
                "to_number": "+34600111222",
                "message": "Recordatorio: cita mañana 09:00",
            }
            result = self.adapter.execute(action)

        assert result["success"] is True
        assert result["provider_message_id"] == "SM_MOCK_123"
        mock_client.messages.create.assert_called_once()

    def test_execute_missing_to_number(self) -> None:
        action: dict[str, Any] = {
            "action_type": "execute_plan",
            "message": "Test",
        }
        result = self.adapter.execute(action)
        assert result["success"] is False
        assert result["error_code"] == "MISSING_PARAMS"

    def test_execute_twilio_exception(self) -> None:
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = RuntimeError("Twilio down")

        with patch.object(self.adapter, "_get_client", return_value=mock_client):
            action: dict[str, Any] = {
                "action_type": "execute_plan",
                "to_number": "+34600111222",
                "message": "Test",
            }
            result = self.adapter.execute(action)

        assert result["success"] is False
        assert "Twilio down" in result["error_message"]
