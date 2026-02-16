"""ROI projection engine — turns simulation data into business metrics.

Produces the exact numbers needed for a dental clinic sales conversation:
baseline loss, recovered revenue, SMS cost, net gain, and annualised ROI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cacp.demo.simulator import SimulationResult

__all__ = ["ROIProjection", "project_roi"]


@dataclass
class ROIProjection:
    """Financial projection from a simulation cohort."""

    # Inputs (echo back for transparency)
    total_appointments: int
    baseline_noshow_rate: float
    avg_ticket_eur: float

    # Baseline (without SMS)
    baseline_noshows: int
    baseline_loss_eur: float

    # After SMS intervention
    noshows_after_sms: int
    noshows_prevented: int
    recovered_revenue_eur: float

    # Cost
    sms_cost_per_message_eur: float
    sms_sent: int
    total_sms_cost_eur: float

    # Net
    net_gain_eur: float
    monthly_roi_percent: float
    annual_projection_eur: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": {
                "total_appointments": self.total_appointments,
                "baseline_noshow_rate": f"{self.baseline_noshow_rate:.1%}",
                "avg_ticket_eur": round(self.avg_ticket_eur, 2),
            },
            "baseline": {
                "noshows": self.baseline_noshows,
                "monthly_loss_eur": round(self.baseline_loss_eur, 2),
            },
            "with_sms": {
                "noshows_after": self.noshows_after_sms,
                "noshows_prevented": self.noshows_prevented,
                "recovered_revenue_eur": round(self.recovered_revenue_eur, 2),
            },
            "cost": {
                "sms_cost_per_message_eur": self.sms_cost_per_message_eur,
                "sms_sent": self.sms_sent,
                "total_sms_cost_eur": round(self.total_sms_cost_eur, 2),
            },
            "roi": {
                "net_gain_monthly_eur": round(self.net_gain_eur, 2),
                "net_gain_annual_eur": round(self.annual_projection_eur, 2),
                "monthly_roi_percent": round(self.monthly_roi_percent, 1),
            },
        }

    def to_executive_summary(self) -> str:
        """One-paragraph pitch-ready text."""
        return (
            f"Con {self.total_appointments} citas mensuales y una tasa de "
            f"no-show del {self.baseline_noshow_rate:.0%}, su clínica pierde "
            f"aproximadamente {self.baseline_loss_eur:,.0f}€ al mes. "
            f"Nuestro sistema de confirmación por SMS previene "
            f"{self.noshows_prevented} inasistencias, recuperando "
            f"{self.recovered_revenue_eur:,.0f}€ mensuales. "
            f"Descontando el coste de SMS ({self.total_sms_cost_eur:,.0f}€), "
            f"el beneficio neto es de {self.net_gain_eur:,.0f}€/mes "
            f"({self.annual_projection_eur:,.0f}€/año)."
        )


def project_roi(
    sim: SimulationResult,
    *,
    sms_cost_per_message: float = 0.07,
) -> ROIProjection:
    """Calculate ROI from simulation results.

    Parameters
    ----------
    sim:
        Output of ``generate_cohort()``.
    sms_cost_per_message:
        Cost per SMS in EUR.  Twilio ES pricing ~0.07€ (2025).
    """
    # Compute real avg ticket from simulation data
    total_ticket = sum(a.ticket_value for a in sim.appointments)
    avg_ticket = total_ticket / max(sim.total, 1)

    baseline_loss = sim.noshow_baseline * avg_ticket
    recovered = sim.noshows_prevented * avg_ticket
    sms_cost_total = sim.sms_sent * sms_cost_per_message
    net = recovered - sms_cost_total
    roi_pct = (net / max(sms_cost_total, 0.01)) * 100

    return ROIProjection(
        total_appointments=sim.total,
        baseline_noshow_rate=sim.noshow_baseline / max(sim.total, 1),
        avg_ticket_eur=avg_ticket,
        baseline_noshows=sim.noshow_baseline,
        baseline_loss_eur=baseline_loss,
        noshows_after_sms=sim.noshow_after_sms,
        noshows_prevented=sim.noshows_prevented,
        recovered_revenue_eur=recovered,
        sms_cost_per_message_eur=sms_cost_per_message,
        sms_sent=sim.sms_sent,
        total_sms_cost_eur=sms_cost_total,
        net_gain_eur=net,
        monthly_roi_percent=roi_pct,
        annual_projection_eur=net * 12,
    )
