"""The chart-derived appservice proposal manifests stay in sync with the chart."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
PROPOSALS = ROOT / "docs" / "notes" / "appservice-proposals"
sys.path.insert(0, str(ROOT / "scripts"))

import render_appservice_proposals as render  # noqa: E402


def test_dashboard_proposal_matches_chart_dashboard() -> None:
    assert render.DASHBOARD_PROPOSAL.read_text() == render.render_dashboard_proposal(), (
        "run: python scripts/render_appservice_proposals.py"
    )


def test_dashboard_proposal_disables_flux_substitution() -> None:
    configmap = yaml.safe_load(render.DASHBOARD_PROPOSAL.read_text())

    # Flux would blank Grafana's ${datasource} variable otherwise.
    assert configmap["metadata"]["annotations"] == {
        "kustomize.toolkit.fluxcd.io/substitute": "disabled"
    }
    dashboard = json.loads(configmap["data"]["homelab-analytics-ops.json"])
    titles = {panel["title"] for panel in dashboard["panels"]}
    assert {"Off-site ship age", "Ingestion success (30d)", "HA bridge connected (30d)"} <= titles


@pytest.mark.skipif(shutil.which("helm") is None, reason="helm is not installed")
def test_rules_proposal_matches_chart_slo_group() -> None:
    assert render.RULES_PROPOSAL.read_text() == render.render_rules_proposal(), (
        "run: python scripts/render_appservice_proposals.py"
    )


def test_rules_proposal_carries_new_slo_alerts() -> None:
    rule = yaml.safe_load(render.RULES_PROPOSAL.read_text())
    rules = rule["spec"]["groups"][0]["rules"]
    alerts = {entry["alert"]: entry for entry in rules if "alert" in entry}
    records = {entry["record"] for entry in rules if "record" in entry}

    assert "homelab_analytics:backup_ship_age_seconds" in records
    assert "homelab_analytics:ingestion_failures:ratio_increase1d" in records
    assert "homelab_analytics:ha_bridge_connected:ratio_avg6h" in records
    assert alerts["HomelabAnalyticsBackupShipStale"]["expr"] == (
        "homelab_analytics:backup_ship_age_seconds > 93600"
    )
    for name in (
        "HomelabAnalyticsBackupShipPending",
        "HomelabAnalyticsBackupShipStalled",
        "HomelabAnalyticsIngestionFailing",
        "HomelabAnalyticsHaBridgeDisconnected",
        "HomelabAnalyticsHaBridgeAvailabilityBurn",
        "HomelabAnalyticsHaBridgeSilent",
    ):
        assert name in alerts
