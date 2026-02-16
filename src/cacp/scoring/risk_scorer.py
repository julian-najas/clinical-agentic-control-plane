"""Deterministic risk scorer for appointment no-show prediction.

Rule-based scorer (v1). No ML — fully auditable and explainable.
Each factor produces a signal in [0, 1]; the weighted sum is the final score.

Thresholds:
    0.00 – 0.29  →  low
    0.30 – 0.59  →  medium
    0.60 – 1.00  →  high
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

__all__ = ["RiskScorer", "RiskResult"]


@dataclass(frozen=True)
class RiskResult:
    """Immutable result of a risk assessment."""

    score: float  # 0.0 – 1.0
    level: str  # "low" | "medium" | "high"
    factors: dict[str, float]  # contribution of each factor


# ── Weights (must sum to 1.0) ────────────────────────────────────────
W_NO_SHOW_HISTORY = 0.40
W_FIRST_VISIT = 0.15
W_LEAD_TIME = 0.15
W_TIME_OF_DAY = 0.10
W_DAY_OF_WEEK = 0.10
W_CONTACT = 0.10


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _level(score: float) -> str:
    if score < 0.3:
        return "low"
    if score < 0.6:
        return "medium"
    return "high"


class RiskScorer:
    """Deterministic no-show risk scorer.

    Factors:
        1. No-show history   — strongest predictor (weight 0.40)
        2. First visit        — new patients no-show 15-25 % more (0.15)
        3. Lead time          — same-day and very-far-out are riskier (0.15)
        4. Time of day        — early morning / late afternoon (0.10)
        5. Day of week        — Monday / Friday (0.10)
        6. Contact available  — unreachable patients are riskier (0.10)
    """

    def score(self, appointment: dict[str, Any]) -> RiskResult:
        """Score an appointment for no-show risk.

        All input fields are optional; sensible fallbacks are used when absent.
        """
        factors: dict[str, float] = {}

        # 1 ── No-show history (0→0, 1→0.5, 2→0.75, 3+→1.0) ─────
        prev = appointment.get("previous_no_shows", 0)
        if prev == 0:
            h = 0.0
        elif prev == 1:
            h = 0.5
        elif prev == 2:
            h = 0.75
        else:
            h = 1.0
        factors["no_show_history"] = h

        # 2 ── First visit ────────────────────────────────────────
        factors["first_visit"] = 0.6 if appointment.get("is_first_visit", False) else 0.0

        # 3 ── Lead time (days until appointment) ─────────────────
        factors["lead_time"] = self._lead_time_signal(
            appointment.get("scheduled_at", "")
        )

        # 4 ── Time of day ────────────────────────────────────────
        hour = self._extract_hour(appointment.get("scheduled_at", ""))
        if hour is not None:
            if hour < 9 or hour >= 17:
                tod = 0.6
            elif hour < 11:
                tod = 0.2
            else:
                tod = 0.1
        else:
            tod = 0.3
        factors["time_of_day"] = tod

        # 5 ── Day of week ────────────────────────────────────────
        dow = self._extract_dow(appointment.get("scheduled_at", ""))
        if dow is not None:
            if dow in (0, 4):  # Monday, Friday
                d = 0.6
            elif dow in (5, 6):  # Weekend
                d = 0.4
            else:
                d = 0.1
        else:
            d = 0.3
        factors["day_of_week"] = d

        # 6 ── Contact availability ───────────────────────────────
        has_phone = bool(appointment.get("patient_phone", ""))
        has_wa = bool(appointment.get("patient_whatsapp", False))
        if has_phone and has_wa:
            c = 0.0
        elif has_phone or has_wa:
            c = 0.3
        else:
            c = 0.8
        factors["contact"] = c

        # ── Weighted sum ─────────────────────────────────────────
        raw = (
            W_NO_SHOW_HISTORY * factors["no_show_history"]
            + W_FIRST_VISIT * factors["first_visit"]
            + W_LEAD_TIME * factors["lead_time"]
            + W_TIME_OF_DAY * factors["time_of_day"]
            + W_DAY_OF_WEEK * factors["day_of_week"]
            + W_CONTACT * factors["contact"]
        )
        final = _clamp(round(raw, 4))

        return RiskResult(score=final, level=_level(final), factors=factors)

    # ── helpers ──────────────────────────────────────────────────
    @staticmethod
    def _lead_time_signal(iso: str) -> float:
        """Same-day → 0.7, 1-3 days → 0.3, 3-14 → 0.1, >14 → 0.5."""
        try:
            scheduled = datetime.fromisoformat(iso)
            now = datetime.now(scheduled.tzinfo)
            days = (scheduled - now).total_seconds() / 86_400
            if days < 1:
                return 0.7
            if days < 3:
                return 0.3
            if days > 14:
                return 0.5
            return 0.1
        except (ValueError, TypeError):
            return 0.3  # unknown → neutral

    @staticmethod
    def _extract_hour(iso: str) -> int | None:
        try:
            return datetime.fromisoformat(iso).hour
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _extract_dow(iso: str) -> int | None:
        try:
            return datetime.fromisoformat(iso).weekday()
        except (ValueError, TypeError):
            return None
