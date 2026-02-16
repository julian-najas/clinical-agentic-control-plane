"""Tests for deterministic risk scorer."""

from __future__ import annotations

from cacp.scoring.risk_scorer import RiskScorer


class TestRiskScorer:
    def setup_method(self) -> None:
        self.scorer = RiskScorer()

    def test_zero_history_low_risk(self) -> None:
        result = self.scorer.score(
            {
                "previous_no_shows": 0,
                "is_first_visit": False,
                "scheduled_at": "2026-03-18T10:00:00+00:00",  # Wednesday
                "patient_phone": "+34600000000",
                "patient_whatsapp": True,
            }
        )
        assert result.level == "low"
        assert result.score < 0.3

    def test_high_history_high_risk(self) -> None:
        result = self.scorer.score(
            {
                "previous_no_shows": 5,
                "is_first_visit": True,
                "scheduled_at": "2026-03-16T08:00:00+00:00",  # Monday early
                "patient_phone": "",
                "patient_whatsapp": False,
            }
        )
        assert result.level == "high"
        assert result.score >= 0.6

    def test_score_between_zero_and_one(self) -> None:
        for ns in range(6):
            result = self.scorer.score({"previous_no_shows": ns})
            assert 0.0 <= result.score <= 1.0

    def test_factors_populated(self) -> None:
        result = self.scorer.score({"previous_no_shows": 2})
        expected_factors = {
            "no_show_history",
            "first_visit",
            "lead_time",
            "time_of_day",
            "day_of_week",
            "contact",
        }
        assert set(result.factors.keys()) == expected_factors

    def test_level_matches_thresholds(self) -> None:
        r = self.scorer.score(
            {
                "previous_no_shows": 0,
                "patient_phone": "+34600",
                "patient_whatsapp": True,
                "scheduled_at": "2026-03-18T10:00:00+00:00",
            }
        )
        assert r.level == "low"
        assert r.score < 0.3

    def test_empty_appointment_does_not_crash(self) -> None:
        result = self.scorer.score({})
        assert 0.0 <= result.score <= 1.0
        assert result.level in ("low", "medium", "high")

    def test_monotonic_with_no_show_count(self) -> None:
        """More past no-shows → higher score (all else equal)."""
        scores = [
            self.scorer.score(
                {
                    "previous_no_shows": n,
                    "scheduled_at": "2026-03-18T10:00:00+00:00",
                    "patient_phone": "+34600",
                    "patient_whatsapp": True,
                }
            ).score
            for n in range(5)
        ]
        for i in range(len(scores) - 1):
            assert scores[i] <= scores[i + 1]
