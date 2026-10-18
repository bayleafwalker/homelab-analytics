# Service Level Objectives

Platform self-observability for homelab-analytics (roadmap B12). These SLOs
describe the platform, not the household data it publishes. The alert rules
in `charts/homelab-analytics/templates/prometheus-rule.yaml` (group `*.slo`)
and the proposed appservice manifests in
[`docs/notes/appservice-proposals/`](../notes/appservice-proposals/README.md)
are generated from the targets below; change both together.

## SLOs and error budgets

All windows are rolling 30 days unless stated.

| SLO | SLI (PromQL source) | Target | Error budget (30d) | Alerts |
|---|---|---|---|---|
| API availability | non-5xx share of API requests, excluding `/metrics`, `/health`, `/ready` (`homelab_analytics_http_requests_total`) | 99.5% | 0.5% of requests (~3.6 h of full outage at constant load) | `ApiErrorBudgetFastBurn` (14.4x over 5m and 1h, critical), `ApiErrorBudgetSlowBurn` (6x over 30m and 6h, warning) |
| API latency | share of the same requests completing within 1 s (`homelab_analytics_http_request_duration_seconds`) | 95% | 5% of requests slower than 1 s | `ApiLatencySloAtRisk` (slow share > 2x budget over 1h for 30m) |
| Source freshness | each source with a freshness config is no more than 24 h past its next expected ingest (`homelab_analytics_source_overdue_seconds`) | 95% of time per source | ~36 h overdue per source | `SourceOverdue` (> 24 h for 1h) |
| Refresh success | publication refreshes that succeed (`homelab_analytics_publication_refresh_duration_seconds_count{outcome}`) | 99% | 1% of refreshes | `PublicationRefreshFailing` (6h error share above budget), `PublicationsUnreliable` (info) |
| Worker liveness | newest worker heartbeat younger than 10 min (`homelab_analytics_worker_last_heartbeat_timestamp_seconds`) | 99.5% of time | ~3.6 h without a heartbeat | `WorkerLoopStalled` (critical) |
| Backup recency | a verified warehouse + landing bundle younger than 26 h (`homelab_analytics_backup_last_success_timestamp_seconds`) | 99% of time | ~7 h past the 26 h limit | `BackupStale`, `BackupFailing` (3 consecutive), `BackupNeverSucceeded` |
| Restore drill | a passing `restore-drill` within 8 days (`homelab_analytics_backup_restore_drill_last_success_timestamp_seconds`) | weekly | one missed week | `RestoreDrillStale` (info) |

Postgres (control plane + reporting) recovery is covered by the hourly
`cnpg-pgdump-age` dumps and the cluster's `cnpg-dump-drill`; see
[backup-and-restore.md](backup-and-restore.md#cnpg-restore-drill-outline).

Burn-rate alerts stay quiet below `minRequestRate` (0.01 req/s) so a single
failed request on an idle homelab instance does not page. Ingestion `rejected`
runs are data problems, not platform errors, and do not count against
refresh success; they show up in source freshness and confidence instead.

### Spending the budget

- Budget left > 50%: ship normally.
- 25-50%: prefer reliability fixes; no risky migrations without a tested
  rollback.
- < 25% or a fast-burn page in the last 7 days: freeze feature releases to
  the cluster until the cause is fixed and the burn rate is back under 1x.

## Metric catalog

API process (`GET /metrics` on the api port; scrape-time collectors run at
most every 15 s):

| Metric | Type | Labels | Meaning |
|---|---|---|---|
| `homelab_analytics_http_requests_total` | counter | `method`, `route` (template), `status` | API requests |
| `homelab_analytics_http_request_duration_seconds` | histogram | `method`, `route`, `status_class` | API latency, buckets 5 ms to 300 s |
| `homelab_analytics_publication_refresh_duration_seconds` | histogram | `outcome` | API-triggered publication refreshes |
| `homelab_analytics_source_freshness_lag_seconds` | gauge | `source_asset_id`, `dataset` | Seconds since the latest landed run |
| `homelab_analytics_source_overdue_seconds` | gauge | `source_asset_id`, `dataset` | Seconds past next expected ingest (0 when on time or unconfigured) |
| `homelab_analytics_source_last_landed_timestamp_seconds` | gauge | `source_asset_id`, `dataset` | Unix time of the latest landed run |
| `homelab_analytics_source_freshness_state` | gauge | `source_asset_id`, `dataset`, `state` | One-hot freshness state |
| `homelab_analytics_publication_confidence_verdicts` | gauge | `verdict` | Publications per latest confidence verdict |
| `homelab_analytics_publication_confidence_verdict` | gauge | `publication_key`, `verdict` | One-hot latest verdict per publication |
| `homelab_analytics_ingestion_runs_recorded_total` | counter | `status` | Runs in run metadata, across processes |
| `homelab_analytics_worker_last_heartbeat_timestamp_seconds` | gauge | | Newest heartbeat from any worker |
| `homelab_analytics_worker_newest_heartbeat_age_seconds` | gauge | | Age of that heartbeat (-1 if none) |
| `homelab_analytics_backup_*` | gauge/counter | | Scheduled-backup status (below) |
| `homelab_analytics_metrics_collector_up` | gauge | `collector` | 1 when a scrape-time collector succeeded |

Worker process (`GET /metrics` on `HOMELAB_ANALYTICS_WORKER_METRICS_PORT`):

| Metric | Type | Labels | Meaning |
|---|---|---|---|
| `homelab_analytics_worker_loop_heartbeat_timestamp_seconds` | gauge | | Latest dispatch-loop iteration |
| `homelab_analytics_worker_loop_iterations_total` | counter | | Loop iterations |
| `homelab_analytics_worker_dispatches_total` | counter | `outcome` | Dispatches completed / failed |
| `homelab_analytics_publication_refresh_duration_seconds` | histogram | `outcome` | Worker-side publication refreshes |
| `homelab_analytics_backup_last_success_timestamp_seconds` | gauge | | Last verified scheduled backup (0 if never) |
| `homelab_analytics_backup_last_attempt_timestamp_seconds`, `_last_failure_timestamp_seconds` | gauge | | Attempt / failure times |
| `homelab_analytics_backup_consecutive_failures` | gauge | | Failures since the last success |
| `homelab_analytics_backup_last_duration_seconds`, `_last_size_bytes`, `_bundles_retained` | gauge | | Last bundle facts |
| `homelab_analytics_backup_successes_total`, `_failures_total` | counter | | From the durable status file |
| `homelab_analytics_backup_restore_drill_last_success_timestamp_seconds`, `_restore_drill_last_passed` | gauge | | Restore drill receipt |

Backup metrics come from `backup-status.json` and `restore-drill-status.json`
in the backup directory, so the API (sharing `/data`) and the worker export
the same values; rules aggregate them with `max()`. The legacy unprefixed
series (`worker_*`, `auth_*`, `ingestion_*`) are unchanged.

## Scrape auth posture

`/metrics` is a public route in the API route policy, like `/health` and
`/ready`: it carries counts and timestamps, never household values. On
appservice the api Service is not routed through the Gateway, and the web
app's own `/metrics` does not proxy the API, so scrapes are network-internal
(NetworkPolicy admits only Prometheus). For defence in depth, set
`HOMELAB_ANALYTICS_METRICS_TOKEN`; both endpoints then require
`Authorization: Metrics <token>` (Prometheus `authorization.type: Metrics`).
A dedicated scheme keeps the token out of the bearer pipeline (service
tokens, machine JWT, OIDC), which would otherwise reject it.

## Dashboard

`charts/homelab-analytics/dashboards/homelab-analytics-ops.json`
(uid `homelab-analytics-ops`): SLO overview with 30-day availability and
budget left, API rate/latency by route, freshness and confidence, ingestion
and refresh outcomes, worker dispatches, backup and drill status, collector
health. The chart ships it as a sidecar ConfigMap
(`monitoring.grafanaDashboard.enabled`); the appservice proposal does the
same in the `kube-prometheus-stack` namespace.

To view it locally against exported metrics: run the API, point a local
Prometheus at `http://127.0.0.1:8080/metrics` with the recording rules from
`helm template ... --show-only templates/prometheus-rule.yaml`, and import
the JSON into Grafana.

## Alert response

| Alert | First checks |
|---|---|
| `ApiErrorBudgetFastBurn` / `SlowBurn` | Dashboard "5xx ratio" and "Latency p95 by route" to find the route; api container logs; `/ready` (control plane / reporting backend reachable?) |
| `ApiLatencySloAtRisk` | Slow route on the dashboard; Postgres load (CNPG); a worker refresh holding locks |
| `SourceOverdue` | `/control/source-freshness`; upload the missing period or fix the ingestion definition |
| `PublicationRefreshFailing` | Worker logs `schedule dispatch processing failed`; `list-schedule-dispatches --status failed` |
| `WorkerLoopStalled` | Worker container restarts/OOM; `list-worker-heartbeats`; stale dispatches |
| `BackupStale` / `BackupFailing` / `BackupNeverSucceeded` | `cat /data/backups/backup-status.json` (`last_error`). "Could not open DuckDB warehouse read-only": another process holds the warehouse write lock; "inside the landing root": fix `HOMELAB_ANALYTICS_BACKUP_DIR`; ENOSPC: the PVC is full, lower retention |
| `RestoreDrillStale` | Run the drill: [backup-and-restore.md](backup-and-restore.md#restore-drill) |
| `MetricsCollectorDown` | API logs `metrics collector failed` with the collector name; the store behind it |
