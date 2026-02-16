"""Dental clinic appointment simulator — generates realistic synthetic data.

Produces a cohort of appointments with probabilistic no-show outcomes
and simulated SMS confirmation results.  Designed to power ROI demos
with numbers that match real dental-clinic behaviour.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any
from zoneinfo import ZoneInfo

__all__ = [
    "AppointmentType",
    "SimulatedAppointment",
    "SimulationResult",
    "generate_cohort",
]


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


class AppointmentType(StrEnum):
    """Common dental appointment categories with realistic ticket values."""

    HYGIENE = "hygiene"
    CHECKUP = "checkup"
    TREATMENT = "treatment"
    EMERGENCY = "emergency"


# Distribution & pricing (Spanish private dental market, 2025)
_TYPE_DISTRIBUTION: dict[AppointmentType, float] = {
    AppointmentType.HYGIENE: 0.30,
    AppointmentType.CHECKUP: 0.25,
    AppointmentType.TREATMENT: 0.35,
    AppointmentType.EMERGENCY: 0.10,
}

_TYPE_TICKET: dict[AppointmentType, float] = {
    AppointmentType.HYGIENE: 60.0,
    AppointmentType.CHECKUP: 50.0,
    AppointmentType.TREATMENT: 120.0,
    AppointmentType.EMERGENCY: 150.0,
}

# No-show probability per type (treatments run higher — longer commitment)
_TYPE_NOSHOW_FACTOR: dict[AppointmentType, float] = {
    AppointmentType.HYGIENE: 1.1,
    AppointmentType.CHECKUP: 0.9,
    AppointmentType.TREATMENT: 1.2,
    AppointmentType.EMERGENCY: 0.5,
}


@dataclass
class SimulatedAppointment:
    """Single synthetic appointment with outcome."""

    appointment_id: str
    patient_id: str
    appointment_type: AppointmentType
    scheduled_at: datetime
    ticket_value: float
    is_noshow_baseline: bool = False
    sms_sent: bool = False
    sms_confirmed: bool = False
    is_noshow_after_sms: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "appointment_id": self.appointment_id,
            "patient_id": self.patient_id,
            "type": self.appointment_type.value,
            "scheduled_at": self.scheduled_at.isoformat(),
            "ticket_eur": self.ticket_value,
            "noshow_baseline": self.is_noshow_baseline,
            "sms_sent": self.sms_sent,
            "sms_confirmed": self.sms_confirmed,
            "noshow_after_sms": self.is_noshow_after_sms,
        }


@dataclass
class SimulationResult:
    """Aggregate result of a full cohort simulation."""

    appointments: list[SimulatedAppointment] = field(default_factory=list)
    total: int = 0
    noshow_baseline: int = 0
    sms_sent: int = 0
    sms_confirmed: int = 0
    noshow_after_sms: int = 0
    noshows_prevented: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_appointments": self.total,
            "noshow_baseline": self.noshow_baseline,
            "noshow_baseline_rate": round(self.noshow_baseline / max(self.total, 1), 4),
            "sms_sent": self.sms_sent,
            "sms_confirmed": self.sms_confirmed,
            "noshow_after_sms": self.noshow_after_sms,
            "noshow_after_sms_rate": round(
                self.noshow_after_sms / max(self.total, 1),
                4,
            ),
            "noshows_prevented": self.noshows_prevented,
        }


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


def _deterministic_patient_id(index: int) -> str:
    """Generate stable pseudo-anonymous patient ID."""
    raw = f"patient-{index}".encode()
    return f"PAT-{hashlib.sha256(raw).hexdigest()[:8].upper()}"


def _pick_type(rng: random.Random) -> AppointmentType:
    """Weighted random appointment type."""
    types = list(_TYPE_DISTRIBUTION.keys())
    weights = list(_TYPE_DISTRIBUTION.values())
    return rng.choices(types, weights=weights, k=1)[0]


def generate_cohort(
    *,
    num_appointments: int = 800,
    baseline_noshow_rate: float = 0.12,
    sms_reduction_rate: float = 0.35,
    sms_confirmation_rate: float = 0.55,
    seed: int | None = 42,
    month_start: datetime | None = None,
    timezone: str = "Europe/Madrid",
) -> SimulationResult:
    """Generate a realistic dental appointment cohort with SMS intervention.

    Parameters
    ----------
    num_appointments:
        Monthly appointment volume.
    baseline_noshow_rate:
        Historical no-show rate without SMS (8%-15% typical dental).
    sms_reduction_rate:
        Fraction of baseline no-shows prevented by SMS confirmation.
        Conservative 25%-40% is realistic; default 35%.
    sms_confirmation_rate:
        Fraction of patients who actively confirm via SMS reply.
    seed:
        Random seed for reproducibility (None for random).
    month_start:
        First day of simulated month.  Defaults to 1st of current month.
    timezone:
        IANA timezone for scheduling.

    Returns
    -------
    SimulationResult with per-appointment detail and aggregate totals.
    """
    rng = random.Random(seed)  # noqa: S311
    tz = ZoneInfo(timezone)

    if month_start is None:
        now = datetime.now(tz)
        month_start = now.replace(day=1, hour=8, minute=0, second=0, microsecond=0)

    # ~200 unique patients for 800 appointments (repeat visitors)
    num_patients = max(num_appointments // 4, 50)

    result = SimulationResult()
    result.total = num_appointments

    for i in range(num_appointments):
        apt_type = _pick_type(rng)
        patient_idx = rng.randint(0, num_patients - 1)

        # Spread appointments across ~22 working days, 8:00-19:00
        day_offset = i * 22 // num_appointments
        hour = rng.randint(8, 18)
        minute = rng.choice([0, 15, 30, 45])
        scheduled = month_start + timedelta(days=day_offset, hours=hour - 8, minutes=minute)

        ticket = _TYPE_TICKET[apt_type]
        # Add ±15% variance to ticket
        ticket = round(ticket * rng.uniform(0.85, 1.15), 2)

        # Baseline no-show (type-weighted)
        noshow_prob = baseline_noshow_rate * _TYPE_NOSHOW_FACTOR[apt_type]
        is_noshow_base = rng.random() < noshow_prob

        # SMS intervention — only for no-show candidates matters,
        # but SMS is sent to everyone
        sms_confirmed = rng.random() < sms_confirmation_rate

        # If was going to no-show AND SMS intervention works
        is_noshow_after = is_noshow_base
        if is_noshow_base and rng.random() < sms_reduction_rate:
            is_noshow_after = False

        apt = SimulatedAppointment(
            appointment_id=f"APT-SIM-{i + 1:04d}",
            patient_id=_deterministic_patient_id(patient_idx),
            appointment_type=apt_type,
            scheduled_at=scheduled,
            ticket_value=ticket,
            is_noshow_baseline=is_noshow_base,
            sms_sent=True,
            sms_confirmed=sms_confirmed,
            is_noshow_after_sms=is_noshow_after,
        )
        result.appointments.append(apt)

        if is_noshow_base:
            result.noshow_baseline += 1
        if sms_confirmed:
            result.sms_confirmed += 1
        if is_noshow_after:
            result.noshow_after_sms += 1

    result.sms_sent = num_appointments
    result.noshows_prevented = result.noshow_baseline - result.noshow_after_sms

    return result
