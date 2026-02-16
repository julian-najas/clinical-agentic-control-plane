"""Tests for ROI projection engine (Sprint 5)."""

from __future__ import annotations

from cacp.demo.roi_projection import project_roi
from cacp.demo.simulator import generate_cohort


class TestProjectROI:
    """ROI calculations from simulation data."""

    def test_basic_projection(self) -> None:
        sim = generate_cohort(
            num_appointments=800,
            baseline_noshow_rate=0.12,
            sms_reduction_rate=0.35,
            seed=42,
        )
        roi = project_roi(sim, sms_cost_per_message=0.07)

        # Basic sanity
        assert roi.total_appointments == 800
        assert roi.baseline_noshows > 0
        assert roi.noshows_prevented > 0
        assert roi.recovered_revenue_eur > 0
        assert roi.net_gain_eur > 0
        assert roi.annual_projection_eur == roi.net_gain_eur * 12

    def test_sms_cost_deducted(self) -> None:
        sim = generate_cohort(num_appointments=100, seed=1)
        roi = project_roi(sim, sms_cost_per_message=0.07)

        assert roi.total_sms_cost_eur == 100 * 0.07
        assert roi.net_gain_eur == roi.recovered_revenue_eur - roi.total_sms_cost_eur

    def test_high_sms_cost_reduces_net(self) -> None:
        sim = generate_cohort(num_appointments=100, seed=1)
        roi_cheap = project_roi(sim, sms_cost_per_message=0.01)
        roi_expensive = project_roi(sim, sms_cost_per_message=0.50)

        assert roi_cheap.net_gain_eur > roi_expensive.net_gain_eur

    def test_zero_noshows_zero_recovery(self) -> None:
        sim = generate_cohort(
            num_appointments=100,
            baseline_noshow_rate=0.001,
            seed=42,
        )
        roi = project_roi(sim)
        # With near-zero no-show rate, recovery should be minimal
        assert roi.baseline_loss_eur < 500  # very small

    def test_to_dict_structure(self) -> None:
        sim = generate_cohort(num_appointments=50, seed=1)
        roi = project_roi(sim)
        d = roi.to_dict()

        assert "summary" in d
        assert "baseline" in d
        assert "with_sms" in d
        assert "cost" in d
        assert "roi" in d
        assert "net_gain_monthly_eur" in d["roi"]
        assert "net_gain_annual_eur" in d["roi"]

    def test_executive_summary_is_string(self) -> None:
        sim = generate_cohort(num_appointments=800, seed=42)
        roi = project_roi(sim)
        summary = roi.to_executive_summary()

        assert isinstance(summary, str)
        assert "€" in summary
        assert "800" in summary

    def test_monthly_roi_positive(self) -> None:
        sim = generate_cohort(
            num_appointments=800,
            baseline_noshow_rate=0.12,
            seed=42,
        )
        roi = project_roi(sim, sms_cost_per_message=0.07)
        # SMS cost is ~56€, recovered revenue should be >> that
        assert roi.monthly_roi_percent > 100
