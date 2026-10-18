"""Regenerate the chart-derived appservice proposal manifests.

docs/notes/appservice-proposals/ carries two files generated from the chart:

- prometheusrule-slo.yaml           the chart's ``*.slo`` rule group (needs helm)
- grafana-dashboard.configmap.yaml  charts/homelab-analytics/dashboards/homelab-analytics-ops.json

Usage::

    python scripts/render_appservice_proposals.py          # rewrite both
    python scripts/render_appservice_proposals.py --check  # exit 1 on drift

tests/test_appservice_proposals.py runs the same comparison.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART_DIR = ROOT / "charts" / "homelab-analytics"
DASHBOARD_JSON = CHART_DIR / "dashboards" / "homelab-analytics-ops.json"
PROPOSALS = ROOT / "docs" / "notes" / "appservice-proposals"
RULES_PROPOSAL = PROPOSALS / "prometheusrule-slo.yaml"
DASHBOARD_PROPOSAL = PROPOSALS / "grafana-dashboard.configmap.yaml"

RULES_HEADER = """\
# GENERATED from charts/homelab-analytics (monitoring.prometheusRule.slo) by
#   python scripts/render_appservice_proposals.py
# which runs
#   helm template homelab-analytics charts/homelab-analytics --namespace analytics \\
#     --set fullnameOverride=homelab-analytics --set monitoring.prometheusRule.enabled=true \\
#     --show-only templates/prometheus-rule.yaml
# keeping only the .slo group. SLO targets: docs/runbooks/slo.md. Validated with
# `promtool check rules`. Target path in appservice:
#   clusters/main/kubernetes/apps/homelab-analytics/app/prometheusrule-slo.yaml
# The chart's runtime group is not proposed: its kube_deployment alerts assume
# separate api/web Deployments, while appservice runs api+worker in one pod.
"""

DASHBOARD_HEADER = """\
# GENERATED from charts/homelab-analytics/dashboards/homelab-analytics-ops.json by
#   python scripts/render_appservice_proposals.py
# Target path in appservice:
#   clusters/main/kubernetes/system/kube-prometheus-stack/app/grafana-dashboard-homelab-analytics.yaml
# (add it to that directory's kustomization.yaml). The kube-prometheus-stack
# Grafana sidecar loads ConfigMaps labelled grafana_dashboard="1" from its
# own namespace by default; keep it there unless sidecar.dashboards.searchNamespace
# is widened. Flux postBuild substitution is disabled on this object: the
# dashboard JSON uses Grafana's own ${datasource} variable, which Flux would
# otherwise replace with an empty string.
"""

SUBSTITUTE_DISABLED = {"kustomize.toolkit.fluxcd.io/substitute": "disabled"}


class _BlockDumper(yaml.SafeDumper):
    pass


def _str_representer(dumper: yaml.SafeDumper, value: str) -> yaml.ScalarNode:
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_BlockDumper.add_representer(str, _str_representer)


def _dump(document: dict[str, Any]) -> str:
    return yaml.dump(document, Dumper=_BlockDumper, sort_keys=False, width=1000)


def render_rules_proposal() -> str:
    rendered = subprocess.run(
        [
            "helm", "template", "homelab-analytics", str(CHART_DIR),
            "--namespace", "analytics",
            "--set", "fullnameOverride=homelab-analytics",
            "--set", "monitoring.prometheusRule.enabled=true",
            "--show-only", "templates/prometheus-rule.yaml",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    rule = yaml.safe_load(rendered)
    slo = next(group for group in rule["spec"]["groups"] if group["name"].endswith(".slo"))
    document = {
        "apiVersion": "monitoring.coreos.com/v1",
        "kind": "PrometheusRule",
        "metadata": {
            "name": "homelab-analytics-slo",
            "namespace": "analytics",
            "labels": {"app.kubernetes.io/name": "homelab-analytics"},
        },
        "spec": {
            "groups": [
                {"name": "appservice.homelab-analytics.slo", "rules": slo["rules"]},
            ]
        },
    }
    return RULES_HEADER + _dump(document)


def render_dashboard_proposal() -> str:
    dashboard = DASHBOARD_JSON.read_text().strip("\n")
    body = "\n".join(f"    {line}" if line else "" for line in dashboard.splitlines())
    metadata = _dump(
        {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": "grafana-dashboard-homelab-analytics-ops",
                "namespace": "kube-prometheus-stack",
                "labels": {
                    "grafana_dashboard": "1",
                    "app.kubernetes.io/name": "homelab-analytics",
                },
                "annotations": dict(SUBSTITUTE_DISABLED),
            },
        }
    )
    return DASHBOARD_HEADER + metadata + "data:\n  homelab-analytics-ops.json: |\n" + body + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="report drift instead of writing")
    parser.add_argument("--skip-rules", action="store_true", help="do not run helm")
    args = parser.parse_args(argv)
    targets = [(DASHBOARD_PROPOSAL, render_dashboard_proposal)]
    if not args.skip_rules:
        targets.append((RULES_PROPOSAL, render_rules_proposal))
    drift = False
    for path, render in targets:
        expected = render()
        if args.check:
            if path.read_text() != expected:
                print(f"{path.relative_to(ROOT)} is out of date", file=sys.stderr)
                drift = True
        else:
            path.write_text(expected)
            print(f"wrote {path.relative_to(ROOT)}")
    return 1 if drift else 0


if __name__ == "__main__":
    raise SystemExit(main())
