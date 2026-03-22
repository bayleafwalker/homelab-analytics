# Backup And Restore

## Scope

The minimum production backup set is:

- Postgres `control` and `reporting` schemas
- landed payloads in S3-compatible object storage
- DuckDB warehouse files only if a worker or local-recovery workflow still depends on them; they are not the primary application production contract

The worker CLI export/import snapshot is a portability tool for control-plane metadata. It is not a replacement for full Postgres backup policy.

## Backup

### Postgres

Take schema-aware dumps with a backup role that can read both schemas:

```bash
pg_dump \
  --format=custom \
  --file /backups/homelab-control-$(date +%F).dump \
  --schema=control \
  --schema=reporting \
  "$HOMELAB_ANALYTICS_CONTROL_PLANE_DSN"
```

If you use separate DSNs per workload, use a dedicated backup DSN rather than reusing API or worker credentials.

### Control-plane JSON snapshot

Keep a periodic portable snapshot for fast local recovery drills:

```bash
python -m apps.worker.main export-control-plane /backups/control-plane-$(date +%F).json
```

### Landed object storage

Mirror the landing prefix with your preferred S3 tool:

```bash
aws s3 sync s3://homelab-landing/bronze /backups/landing/bronze
```

or:

```bash
mc mirror myminio/homelab-landing/bronze /backups/landing/bronze
```

### DuckDB artifacts

If you still rely on local warehouse recovery, copy the DuckDB file only while the worker is stopped or the PVC is snapshotted:

```bash
cp /data/analytics/warehouse.duckdb /backups/warehouse-$(date +%F).duckdb
```

## Restore

1. Stop worker queue consumers first.
2. Restore Postgres schemas:

```bash
pg_restore \
  --clean \
  --if-exists \
  --no-owner \
  --dbname "$HOMELAB_ANALYTICS_CONTROL_PLANE_DSN" \
  /backups/homelab-control-2026-03-15.dump
```

3. Restore landed object data from the mirrored backup.
4. Restore DuckDB artifacts only if the recovery plan still depends on local warehouse state.
5. Resume workers after `/ready` succeeds for API and web.

Use JSON import only for controlled bootstrap/local recovery:

```bash
python -m apps.worker.main import-control-plane /backups/control-plane-2026-03-15.json
```

Do not import a snapshot into a live Postgres-backed environment that already contains newer control-plane state.

## Post-restore validation

Run these checks after any restore:

```bash
curl -fsS http://127.0.0.1:8080/ready
python -m apps.worker.main list-runs
python -m apps.worker.main list-schedule-dispatches
python -m apps.worker.main list-worker-heartbeats
```

Then confirm in the web control plane:

- recent runs are visible
- schedule dispatch history is present
- source lineage and publication audit data load successfully
- `/metrics` no longer reports stale workers caused by the restore window
