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
| Off-site shipment | a bundle shipped off-site (encrypted, size-checked in the Object-Lock bucket) within 26 h (`homelab_analytics_backup_ship_last_success_timestamp_seconds`, from the `backup-ship` sidecar's `ship-status.json`) | 99% of time | ~7 h past the 26 h limit | `BackupShipStale`, `BackupShipPending` (a verified bundle unshipped for 2 h), `BackupShipStalled` (no sidecar pass for 1 h) |
| Restore drill | a passing `restore-drill` within 8 days (`homelab_analytics_backup_restore_drill_last_success_timestamp_seconds`) | weekly | one missed week | `RestoreDrillStale` (info) |
| Ingestion success | landed share of ingestion runs that finished landed or failed (`homelab_analytics_ingestion_runs_recorded_total{status}`); `rejected` and in-flight `received` runs are excluded | 98% | 2% of finished runs | `IngestionFailing` (failed share > 5x budget, i.e. 10%, over 1 d with at least 3 runs, for 1 h) |
| HA bridge availability | share of time the Home Assistant WebSocket bridge is connected (`homelab_analytics_ha_bridge_connected`); only where the API runs a bridge | 99% of time | ~7.2 h disconnected | `HaBridgeDisconnected` (15 min), `HaBridgeAvailabilityBurn` (< 94% connected over 6 h: flapping), `HaBridgeSilent` (connected but no `state_changed` message for 1 h) |

Postgres (control plane + reporting) recovery is covered by the hourly
`cnpg-pgdump-age` dumps and the cluster's `cnpg-dump-drill`; see
[backup-and-restore.md](backup-and-restore.md#cnpg-restore-drill).

Burn-rate alerts stay quiet below `minRequestRate` (0.01 req/s) so a single
failed request on an idle homelab instance does not page. Ingestion `rejected`
runs are data problems, not platform errors, and count against neither
refresh success nor ingestion success; they show up in source freshness and
confidence instead. Ingestion success counts `failed` runs (the platform could
not land a valid payload) against `landed` ones. A homelab lands a handful of
runs a day, so `IngestionFailing` needs at least `ingestionMinRunsPerDay` (3)
finished runs in the day before one failure can page.

The shipment and HA bridge alerts are silent where their source does not
exist: without a `backup-ship` sidecar there is no `ship-status.json` (only
`homelab_analytics_backup_ship_status_present 0` is exported), and without a
bridge only `homelab_analytics_ha_bridge_enabled 0` is.

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
| `homelab_analytics_backup_*` | gauge/counter | | Scheduled-backup and off-site shipment status (below) |
| `homelab_analytics_ha_bridge_enabled` | gauge | | 1 when this API process runs the Home Assistant bridge |
| `homelab_analytics_ha_bridge_connected` | gauge | | 1 while the bridge is connected and subscribed (same source as `GET /api/ha/bridge/status`) |
| `homelab_analytics_ha_bridge_last_message_timestamp_seconds` | gauge | | Last ingested `state_changed` message (0 if none) |
| `homelab_analytics_ha_bridge_last_message_age_seconds` | gauge | | Age of that message (-1 if none since API start) |
| `homelab_analytics_ha_bridge_reconnects_total` | counter | | Bridge reconnects since API start |
| `homelab_analytics_metrics_collector_up` | gauge | `collector` | 1 when a scrape-time collector succeeded |
| `homelab_analytics_api_warehouse_handle_open` | gauge | `mode` (`read_only`, `read_write`) | 1 while the API process holds a DuckDB warehouse handle; normally 0 between requests |
| `homelab_analytics_api_warehouse_opens_total` | counter | `mode` | Short-lived warehouse handles opened by the API |
| `homelab_analytics_api_warehouse_busy_total` | counter | | API warehouse opens that hit a lock held by another process for the whole retry window (answered 503) |

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
| `homelab_analytics_backup_ship_status_present` | gauge | | 1 when `ship-status.json` exists |
| `homelab_analytics_backup_ship_last_success_timestamp_seconds` | gauge | | Last bundle shipped off-site and size-checked (0 if never) |
| `homelab_analytics_backup_ship_last_attempt_timestamp_seconds`, `_last_failure_timestamp_seconds` | gauge | | Upload attempt / failed pass times |
| `homelab_analytics_backup_ship_last_pass_timestamp_seconds` | gauge | | Sidecar liveness: last finished pass |
| `homelab_analytics_backup_ship_consecutive_failures`, `_last_size_bytes` | gauge | | Failed passes since a clean one; encrypted size of the last shipped bundle |
| `homelab_analytics_backup_ship_pending_bundles` | gauge | | Complete local bundles not in `.shipped` |
| `homelab_analytics_backup_ship_shipped_total`, `_failures_total` | counter | | From the durable status file |

Backup metrics come from `backup-status.json`, `restore-drill-status.json` and
`ship-status.json` (plus `.shipped`) in the backup directory, so the API (sharing `/data`) and the worker export
the same values; rules aggregate them with `max()`. The legacy unprefixed
series (`worker_*`, `auth_*`, `ingestion_*`) are unchanged apart from two
naming fixes.

### Removed metric names (0.1.6)

Two legacy API series broke the Prometheus naming rules (`_total` is only for
counters, and every counter ends in `_total`). Release 0.1.5 emitted
the new name next to the old one; 0.1.6 removes the old names. Dashboards or
recording rules that still query them get no data. The chart rules, the ops
dashboard and the appservice proposal copies never used them.

| Removed | Replacement | Type | Status | Why |
|---|---|---|---|---|
| `auth_service_tokens_total` | `auth_service_tokens` | gauge | removed in 0.1.6 | A token count that can go down is a gauge; `_total` implies a counter |
| `ingestion_duration_seconds` | `ingestion_duration_seconds_total` | counter | removed in 0.1.6 | Cumulative seconds is a counter and needs the `_total` suffix |

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
budget left, off-site ship age, ingestion success and its budget, HA bridge
availability, API rate/latency by route, freshness and confidence, ingestion
and refresh outcomes, worker dispatches, backup and drill status, collector
health. The appservice copy is generated:
`python scripts/render_appservice_proposals.py` (needs `helm` for the rules
file; `tests/test_appservice_proposals.py` fails on drift). The chart ships it as a sidecar ConfigMap
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
| 503 responses with `Retry-After` | A worker promotion held the warehouse write lock longer than the API retry window; `homelab_analytics_api_warehouse_busy_total` rises. Short bursts during promotions are expected and spend the availability budget |
| `ApiLatencySloAtRisk` | Slow route on the dashboard; Postgres load (CNPG); a worker refresh holding locks |
| `SourceOverdue` | `/control/source-freshness`; upload the missing period or fix the ingestion definition |
| `PublicationRefreshFailing` | Worker logs `schedule dispatch processing failed`; `list-schedule-dispatches --status failed` |
| `WorkerLoopStalled` | Worker container restarts/OOM; `list-worker-heartbeats`; stale dispatches |
| `BackupStale` / `BackupFailing` / `BackupNeverSucceeded` | `cat /data/backups/backup-status.json` (`last_error`). "Could not open DuckDB warehouse read-only": a writer held the lock through the backup's retry window (about 7.5 s) — a long worker promotion; check `homelab_analytics_api_warehouse_handle_open` (the API only holds short-lived handles); "inside the landing root": fix `HOMELAB_ANALYTICS_BACKUP_DIR`; ENOSPC: the PVC is full, lower retention |
| `RestoreDrillStale` | Run the drill: [backup-and-restore.md](backup-and-restore.md#restore-drill) |
| `BackupShipStale` / `BackupShipPending` | `cat /data/backups/ship-status.json` (`last_error`, `consecutive_failures`) and `kubectl logs ... -c backup-ship`. "age not available": GitHub unreachable (egress policy); "shipping ... failed": Hetzner credentials or endpoint; "implausibly small": the upload truncated. `BackupStale` firing too means there was nothing new to ship |
| `BackupShipStalled` | The `backup-ship` container is not running or an upload hangs; its restart count and log |
| `IngestionFailing` | `homelab-analytics-worker list-runs` for `failed` runs and their errors; landing volume full; a source format change shows as `rejected`, not here |
| `HaBridgeDisconnected` / `HaBridgeAvailabilityBurn` | `GET /api/ha/bridge/status` (`reconnect_count`); Home Assistant reachable from the api pod; HA long-lived token still valid |
| `HaBridgeSilent` | Connected but no `state_changed` events: the subscription died without a disconnect. Restart the api container if Home Assistant is producing events |
| `MetricsCollectorDown` | API logs `metrics collector failed` with the collector name; the store behind it |
