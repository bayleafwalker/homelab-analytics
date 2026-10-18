# appservice proposals: observability, SLO alerts, scheduled backups

Proposed manifests for `bayleafwalker/appservice`, closing the open first-rollout
follow-ups in [appservice-cluster-integration-notes.md](../appservice-cluster-integration-notes.md#realized-first-rollout-2026-08-29):
Prometheus metrics and alert rules, the gatus check, and backup of the DuckDB
warehouse + filesystem landing that `cnpg-pgdump-age` does not cover. This repo
does not write to appservice; copy these files in a GitOps PR and let Flux
reconcile.

## Precondition

A homelab-analytics release (image + attested digest) that contains branch
`feat/ops-observability-backup`. v0.1.2 has neither the worker metrics port,
the `homelab_analytics_*` series, nor scheduled backups. `deployment.yaml`
carries `sha256:REPLACE_WITH_RELEASE_DIGEST` on purpose so it cannot be
applied unpinned.

## Files

| File here | Target in appservice (`clusters/main/kubernetes/`) | What it does |
|---|---|---|
| `deployment.yaml` | `apps/homelab-analytics/app/deployment.yaml` (replace the first document) | New digest; worker metrics port 9464; daily scheduled backup (retention 3) into `/data/backups`; `backup-ship` sidecar (tar \| age \| rclone to `appservice-pgdump-locked`, prefix `backups/app-bundles/analytics/homelab-analytics/`, 30-day remote retention under Object Lock) that writes `/data/backups/ship-status.json` after every pass for the off-site shipment SLO |
| `podmonitor.yaml` | `apps/homelab-analytics/app/podmonitor.yaml` | Scrape api `:8080/metrics` and worker `:9464/metrics` |
| `prometheusrule-slo.yaml` | `apps/homelab-analytics/app/prometheusrule-slo.yaml` | SLO recording rules + burn-rate/freshness/refresh/worker/backup/off-site shipment/ingestion success/HA bridge alerts (generated from the chart; `promtool check rules` passes) |
| `networkpolicy-observability.cnp.yaml` | `apps/homelab-analytics/app/` | Ingress from Prometheus (8080, 9464) and gatus (8080 api, 8081 web) |
| `networkpolicy-backup-ship.cnp.yaml` | `apps/homelab-analytics/app/` | Egress 443 to GitHub (age release) and the Hetzner endpoint only, via toFQDNs |
| `gatus-endpoints.yaml` | append to `apps/gatus/app/configmap.yaml` | `/ready` checks for api (status + body + latency) and web |
| `grafana-dashboard.configmap.yaml` | `system/kube-prometheus-stack/app/grafana-dashboard-homelab-analytics.yaml` | Ops/SLO dashboard for the Grafana sidecar (`grafana_dashboard: "1"`); Flux substitution disabled so Grafana's `${datasource}` variable survives |

Add the four new `apps/homelab-analytics/app/` files to that directory's
`kustomization.yaml` `resources`, and the dashboard to
`system/kube-prometheus-stack/app/kustomization.yaml`.

`prometheusrule-slo.yaml` and `grafana-dashboard.configmap.yaml` are
generated: change the chart, then run
`python scripts/render_appservice_proposals.py` (needs `helm`);
`tests/test_appservice_proposals.py` fails on drift. Everything here goes
through the cluster-wide Flux postBuild substitution, so scripts in these
manifests use `$var`, never the dollar-brace form, which Flux would blank.

## Order

1. Publish the release; take its digest.
2. PR 1 (safe, no behaviour change for users): `networkpolicy-observability`,
   `podmonitor`, `prometheusrule-slo`, gatus endpoints, dashboard, and the new
   digest in `deployment.yaml` with the `backup-ship` container and the
   `HOMELAB_ANALYTICS_BACKUP_*` env lines left out.
3. PR 2: backup env + `backup-ship` + `networkpolicy-backup-ship`.

## Verify after reconcile

- Prometheus targets: two `analytics/homelab-analytics` endpoints UP;
  `homelab_analytics_http_requests_total` and
  `homelab_analytics_worker_loop_heartbeat_timestamp_seconds` present.
- gatus shows "Homelab Analytics API" green.
- Within one poll interval after the first idle loop iteration:
  `/data/backups/backup-<stamp>/` exists and `backup-status.json` has
  `last_success_at`; `homelab_analytics_backup_last_success_timestamp_seconds`
  is non-zero; the `backup-ship` log prints `shipped backup-<stamp>.tar.age`.
- Within one ship interval (15 min) after that:
  `/data/backups/ship-status.json` has `last_success_at` and
  `"consecutive_failures": 0`;
  `homelab_analytics_backup_ship_last_success_timestamp_seconds` is non-zero
  and `homelab_analytics_backup_ship_pending_bundles` is 0.
- Drill: `homelab-analytics-worker restore-drill` in the worker container
  prints `"passed": true`
  ([runbook](../../runbooks/backup-and-restore.md#restore-drill)).

If `backup-status.json` shows `Could not open DuckDB warehouse read-only`, a
writer held the DuckDB lock through the whole retry window (about 7.5 s). The
api only holds short-lived handles (read-only for reads, read-write for the
duration of a write), so this means a long write; the worker retries after
15 minutes and `HomelabAnalyticsBackupFailing` fires after three failures.
`homelab_analytics_api_warehouse_handle_open{mode}` on the api shows whether the
api holds a handle at scrape time.

## Not included

- The chart's runtime alert group (its `kube_deployment` expressions assume
  separate api/web Deployments).
- A CNPG restore-drill CronJob: outline only, in
  [backup-and-restore.md](../../runbooks/backup-and-restore.md#cnpg-restore-drill-outline).
- A dedicated Hetzner key scoped to the app-bundles prefix (the sidecar reuses
  `analytics-cnpg-backup-s3`, like `cnpg-pgdump-age`).
