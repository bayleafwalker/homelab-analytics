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
| `cronjob-cnpg-restore-drill.yaml` | `system/cnpg-dump-drill/app/homelab-analytics-restore-drill.yaml` | Weekly app-level restore drill (ConfigMap scripts + CronJob): newest analytics dump into a scratch Postgres sidecar, schema-head / worker / api checks with the release image, plus `restore-drill` on the newest shipped bundle; one JSON receipt line ([runbook](../../runbooks/backup-and-restore.md#cnpg-restore-drill)) |
| `secret-app-bundles-s3.template.yaml` | `apps/homelab-analytics/app/homelab-analytics-bundles-s3.secret.yaml` (filled in, then SOPS-encrypted) | Dedicated S3 credential for `backup-ship`; placeholders only |
| `bucket-policy-app-bundles.template.json` | not a manifest: merged into the `appservice-pgdump-locked` bucket policy by the operator | Explicit denies that confine the dedicated key to `backups/app-bundles/analytics/homelab-analytics/` |

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
4. PR 3, after the first bundle shipped (`homelab_analytics_backup_ship_last_success_timestamp_seconds`
   non-zero): `cronjob-cnpg-restore-drill.yaml` (same release digest as
   `deployment.yaml`) and the `system/cnpg-dump-drill/app/kustomization.yaml`
   entry. Then run it once by hand (below) instead of waiting for Sunday.
5. PR 4 (optional hardening): the dedicated app-bundles key
   ([below](#dedicated-app-bundles-s3-key)).

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

## CNPG restore drill

Manual first run after PR 3 reconciles (operator; `cnpg-dump-drill` has no
agent-access binding by design):

```bash
kubectl -n cnpg-dump-drill create job --from=cronjob/homelab-analytics-restore-drill ha-drill-manual-$(date +%H%M)
kubectl -n cnpg-dump-drill logs -f job/ha-drill-manual-<HHMM> -c restore
kubectl -n cnpg-dump-drill logs -f job/ha-drill-manual-<HHMM> -c app-check
```

Expected: `restore` prints `OK   restored analytics-postgres-homelab_analytics-<stamp>.dump.age`
and `OK   fetched backup-<stamp>`; the last `app-check` line is
`{"cnpg_restore_drill": {... "passed": true ...}}` and the Job completes.
Send back that JSON line. A `schema_heads` failure means the dump predates
the release's migrations (run the drill after the release's `migrate`
initContainer ran on the live cluster).

## Dedicated app-bundles S3 key

Optional hardening. The 2026-09-19 operator decision (agentops#2408, event
2989) chose the Object-Lock bucket over dedicated keys for the pgdump path,
and `backup-ship` follows that today with the shared
`analytics-cnpg-backup-s3`. Object Lock already stops a leaked key from
erasing recent bundles; a dedicated key additionally stops the app pod's
credential from reading the pgdump series. Hetzner keys are valid for every
bucket in their project, so the confinement comes from explicit bucket-policy
denies, the same pattern as the etcd max-age monitor key; other buckets in
the project stay reachable unless the key lives in its own project.

1. Hetzner console, project that owns `appservice-pgdump-locked`: create an S3
   credential named `homelab-analytics-app-bundles`. Keep the secret key out
   of shell history and Git.
2. Merge `bucket-policy-app-bundles.template.json` into the bucket policy
   with the admin key, after replacing `REPLACE_WITH_PRINCIPAL_OF_APP_BUNDLES_KEY`
   with that credential's principal in the format Hetzner's bucket-policy
   documentation gives:
   ```bash
   aws --endpoint-url "https://$HETZNER_S3_BUCKET_ENDPOINT" s3api get-bucket-policy \
     --bucket appservice-pgdump-locked --query Policy --output text > current.json
   # append the four statements to current.json's "Statement" array, then:
   aws --endpoint-url "https://$HETZNER_S3_BUCKET_ENDPOINT" s3api put-bucket-policy \
     --bucket appservice-pgdump-locked --policy file://current.json
   ```
3. Verify with the new key (`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` set to
   it): `aws s3 ls s3://appservice-pgdump-locked/backups/app-bundles/analytics/homelab-analytics/`
   lists bundles; `aws s3 ls s3://appservice-pgdump-locked/backups/pgdump-age/`
   and `aws s3api get-bucket-policy --bucket appservice-pgdump-locked` are
   `AccessDenied`.
4. appservice PR: copy `secret-app-bundles-s3.template.yaml` to
   `apps/homelab-analytics/app/homelab-analytics-bundles-s3.secret.yaml`, fill
   in the two values, `sops --encrypt --in-place` it, add it to the app
   `kustomization.yaml`, and in `deployment.yaml` change the two `backup-ship`
   `secretKeyRef.name` values from `analytics-cnpg-backup-s3` to
   `homelab-analytics-bundles-s3`.
5. After reconcile: the next `backup-ship` pass logs `shipped ...` (or, with
   nothing new, `ship-status.json` `last_pass_at` advances with
   `"consecutive_failures": 0`). `cnpg-dump-drill`'s `drill-s3` keeps the
   shared key, so the restore drill still reads both prefixes.

## Not included

- The chart's runtime alert group (its `kube_deployment` expressions assume
  separate api/web Deployments).
