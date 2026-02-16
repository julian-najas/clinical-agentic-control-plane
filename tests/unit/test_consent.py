"""Tests for consent model + in-memory store."""

from __future__ import annotations

from cacp.consent import InMemoryConsentStore, hash_pii


class TestHashPii:
    def test_deterministic(self) -> None:
        assert hash_pii("+34600000000") == hash_pii("+34600000000")

    def test_different_inputs_different_hashes(self) -> None:
        assert hash_pii("+34600000000") != hash_pii("+34600000001")

    def test_length_16(self) -> None:
        assert len(hash_pii("anything")) == 16


class TestInMemoryConsentStore:
    def setup_method(self) -> None:
        self.store = InMemoryConsentStore()

    def test_no_consent_by_default(self) -> None:
        assert not self.store.has_consent("PAT-001", "sms")

    def test_grant_then_check(self) -> None:
        self.store.grant("PAT-001", "sms")
        assert self.store.has_consent("PAT-001", "sms")

    def test_grant_does_not_leak_to_other_channel(self) -> None:
        self.store.grant("PAT-001", "sms")
        assert not self.store.has_consent("PAT-001", "whatsapp")

    def test_revoke_removes_consent(self) -> None:
        self.store.grant("PAT-001", "sms")
        self.store.revoke("PAT-001", "sms")
        assert not self.store.has_consent("PAT-001", "sms")

    def test_revoke_nonexistent_is_noop(self) -> None:
        self.store.revoke("PAT-999", "sms")
        assert not self.store.has_consent("PAT-999", "sms")

    def test_re_grant_after_revoke(self) -> None:
        self.store.grant("PAT-001", "sms")
        self.store.revoke("PAT-001", "sms")
        self.store.grant("PAT-001", "sms")
        assert self.store.has_consent("PAT-001", "sms")

    def test_load_from_appointment(self) -> None:
        appointment = {
            "patient_id": "PAT-001",
            "consent_given": True,
            "patient_phone": "+34600000000",
            "patient_whatsapp": True,
        }
        self.store.load_from_appointment(appointment)
        assert self.store.has_consent("PAT-001", "sms")
        assert self.store.has_consent("PAT-001", "whatsapp")

    def test_load_without_consent_does_not_grant(self) -> None:
        appointment = {
            "patient_id": "PAT-002",
            "consent_given": False,
            "patient_phone": "+34600000000",
        }
        self.store.load_from_appointment(appointment)
        assert not self.store.has_consent("PAT-002", "sms")
