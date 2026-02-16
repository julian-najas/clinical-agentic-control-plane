"""Tests for dental clinic simulator (Sprint 5)."""

from __future__ import annotations

from cacp.demo.simulator import (
    AppointmentType,
    generate_cohort,
)


class TestGenerateCohort:
    """Cohort generation with deterministic seed."""

    def test_default_800_appointments(self) -> None:
        result = generate_cohort()
        assert result.total == 800
        assert len(result.appointments) == 800

    def test_custom_count(self) -> None:
        result = generate_cohort(num_appointments=100, seed=1)
        assert result.total == 100
        assert len(result.appointments) == 100

    def test_deterministic_with_seed(self) -> None:
        r1 = generate_cohort(seed=99)
        r2 = generate_cohort(seed=99)
        ids_1 = [a.appointment_id for a in r1.appointments]
        ids_2 = [a.appointment_id for a in r2.appointments]
        assert ids_1 == ids_2
        assert r1.noshow_baseline == r2.noshow_baseline
        assert r1.noshows_prevented == r2.noshows_prevented

    def test_noshow_rate_in_expected_range(self) -> None:
        result = generate_cohort(
            num_appointments=5000,
            baseline_noshow_rate=0.12,
            seed=42,
        )
        rate = result.noshow_baseline / result.total
        # With 5000 appointments, rate should be close to 12% (±4%)
        assert 0.08 < rate < 0.16

    def test_sms_always_sent(self) -> None:
        result = generate_cohort(num_appointments=50, seed=7)
        assert result.sms_sent == 50
        assert all(a.sms_sent for a in result.appointments)

    def test_noshows_prevented_positive(self) -> None:
        result = generate_cohort(
            num_appointments=1000,
            baseline_noshow_rate=0.12,
            sms_reduction_rate=0.35,
            seed=42,
        )
        assert result.noshows_prevented > 0
        assert result.noshow_after_sms < result.noshow_baseline

    def test_appointment_types_distributed(self) -> None:
        result = generate_cohort(num_appointments=1000, seed=42)
        types_seen = {a.appointment_type for a in result.appointments}
        assert AppointmentType.HYGIENE in types_seen
        assert AppointmentType.CHECKUP in types_seen
        assert AppointmentType.TREATMENT in types_seen
        assert AppointmentType.EMERGENCY in types_seen

    def test_ticket_values_have_variance(self) -> None:
        result = generate_cohort(num_appointments=100, seed=42)
        tickets = [a.ticket_value for a in result.appointments]
        # Not all the same
        assert len(set(tickets)) > 10

    def test_patient_ids_are_stable(self) -> None:
        """Same seed → same patient IDs."""
        r1 = generate_cohort(num_appointments=10, seed=5)
        r2 = generate_cohort(num_appointments=10, seed=5)
        pids_1 = [a.patient_id for a in r1.appointments]
        pids_2 = [a.patient_id for a in r2.appointments]
        assert pids_1 == pids_2

    def test_to_dict_keys(self) -> None:
        result = generate_cohort(num_appointments=5, seed=1)
        d = result.to_dict()
        assert "total_appointments" in d
        assert "noshow_baseline" in d
        assert "noshows_prevented" in d

    def test_simulation_result_consistency(self) -> None:
        result = generate_cohort(num_appointments=500, seed=42)
        assert result.noshows_prevented == result.noshow_baseline - result.noshow_after_sms
        assert result.noshow_after_sms <= result.noshow_baseline
