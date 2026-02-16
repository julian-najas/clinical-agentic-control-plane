"""Tests for gitops manifest builder."""

from __future__ import annotations

from cacp.gitops.manifest import build_plan_manifest


class TestBuildPlanManifest:
    def test_contains_required_fields(self) -> None:
        actions = [{"action_type": "send_reminder", "channel": "sms"}]
        manifest = build_plan_manifest(
            appointment_id="APT-100",
            actions=actions,
            hmac_signature="abc123",
        )
        assert manifest["appointment_id"] == "APT-100"
        assert manifest["actions"] == actions
        assert manifest["hmac"] == "abc123"
        assert "created_at" in manifest
        assert "version" in manifest

    def test_risk_level_included(self) -> None:
        manifest = build_plan_manifest(
            appointment_id="APT-200",
            actions=[],
            hmac_signature="def456",
            risk_level="high",
        )
        assert manifest["risk_level"] == "high"
