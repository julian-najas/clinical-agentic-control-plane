"""Patient consent model — in-memory store for MVP."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

__all__ = [
    "ConsentRecord",
    "ConsentStoreProtocol",
    "InMemoryConsentStore",
    "hash_pii",
]


def hash_pii(value: str) -> str:
    """One-way hash for PII (phone, email) — never store in clear."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class ConsentRecord:
    """Immutable consent snapshot."""

    patient_id: str
    channel: str  # "sms" | "whatsapp" | "email"
    granted_at: str
    revoked_at: str | None = None

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None


class ConsentStoreProtocol(Protocol):
    """Minimal contract for consent lookups."""

    def has_consent(self, patient_id: str, channel: str) -> bool:
        """Return True if patient has active consent for channel."""
        ...

    def grant(self, patient_id: str, channel: str) -> None:
        """Record consent grant."""
        ...

    def revoke(self, patient_id: str, channel: str) -> None:
        """Record consent revocation."""
        ...


class InMemoryConsentStore:
    """In-memory consent store for dev/test."""

    def __init__(self) -> None:
        self._records: dict[str, ConsentRecord] = {}

    def _key(self, patient_id: str, channel: str) -> str:
        return f"{patient_id}:{channel}"

    def has_consent(self, patient_id: str, channel: str) -> bool:
        record = self._records.get(self._key(patient_id, channel))
        return record is not None and record.is_active

    def grant(self, patient_id: str, channel: str) -> None:
        self._records[self._key(patient_id, channel)] = ConsentRecord(
            patient_id=patient_id,
            channel=channel,
            granted_at=datetime.now(UTC).isoformat(),
        )

    def revoke(self, patient_id: str, channel: str) -> None:
        key = self._key(patient_id, channel)
        existing = self._records.get(key)
        if existing and existing.is_active:
            self._records[key] = ConsentRecord(
                patient_id=existing.patient_id,
                channel=existing.channel,
                granted_at=existing.granted_at,
                revoked_at=datetime.now(UTC).isoformat(),
            )

    def load_from_appointment(self, appointment: dict[str, Any]) -> None:
        """Bootstrap consent from appointment payload (dev convenience).

        If appointment has consent_given=True and a phone, grant sms.
        Real system would have a dedicated consent service.
        """
        patient_id = appointment.get("patient_id", "")
        if not patient_id:
            return
        if appointment.get("consent_given"):
            if appointment.get("patient_phone"):
                self.grant(patient_id, "sms")
            if appointment.get("patient_whatsapp"):
                self.grant(patient_id, "whatsapp")
