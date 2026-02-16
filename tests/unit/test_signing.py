"""Tests for HMAC signing module."""

from __future__ import annotations

from cacp.signing.canonical import canonicalise
from cacp.signing.hmac import sign_payload, verify_signature


class TestCanonicalise:
    def test_sorted_keys(self) -> None:
        result = canonicalise({"z": 1, "a": 2})
        assert result == '{"a":2,"z":1}'

    def test_exclude_keys(self) -> None:
        result = canonicalise({"a": 1, "hmac": "xxx", "b": 2}, exclude_keys={"hmac"})
        assert result == '{"a":1,"b":2}'

    def test_nested_sorting(self) -> None:
        result = canonicalise({"b": {"z": 1, "a": 2}, "a": 0})
        assert '"a":0' in result
        assert result.index('"a":0') < result.index('"b":')

    def test_deterministic(self) -> None:
        payload = {"action": "send_sms", "patient": "P1", "time": "09:00"}
        assert canonicalise(payload) == canonicalise(payload)


class TestHMACSign:
    def test_sign_and_verify(self) -> None:
        payload = {"action": "send_sms", "patient": "P1"}
        secret = "test-secret"
        sig = sign_payload(payload, secret)
        assert verify_signature(payload, secret, sig)

    def test_wrong_secret_fails(self) -> None:
        payload = {"action": "send_sms"}
        sig = sign_payload(payload, "secret-a")
        assert not verify_signature(payload, "secret-b", sig)

    def test_tampered_payload_fails(self) -> None:
        payload = {"action": "send_sms"}
        sig = sign_payload(payload, "secret")
        payload["action"] = "send_whatsapp"
        assert not verify_signature(payload, "secret", sig)

    def test_signature_is_hex_string(self) -> None:
        sig = sign_payload({"a": 1}, "s")
        assert all(c in "0123456789abcdef" for c in sig)
