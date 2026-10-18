# Backup And Restore

## Scope

State lives in four places. Which tool backs each one up depends on the backend:

| Store | SQLite / filesystem deployments (single-user Compose, demo/dev) | Shared Postgres deployments (appservice) |
|---|---|---|
| Control plane + run metadata | `worker backup` (SQLite `config.db`) | `pg_dump` of the `control` schema (CNPG backup CronJob) |
| Reporting marts | `worker backup` (DuckDB warehouse) | `pg_dump` of the `reporting` schema |
| DuckDB warehouse (transformation + reporting) | `worker backup` | `worker backup`, if a worker or local-recovery workflow still depends on the PVC |
| Landed payloads | `worker backup` (filesystem `landing_root`) | Object-storage mirror (`aws s3 sync` / `mc mirror`) |

`worker backup` is the app-level bundle. It covers the file-backed stores that `pg_dump` does not. It does not replace Postgres backup policy. Postgres and S3 stores are listed in the manifest as excluded components, with the reason.

Not covered by any app command: the `inbox/`, `processed/` and `failed/` watched-folder directories, the external-registry cache (rebuilt on sync), and secret values (environment variables, mounted secret files, Kubernetes Secrets). Back those up with your platform tooling.

## Worker backup bundle

### What a bundle contains

```text
<backup-dir>/
  manifest.json                    format, format_version, created_at, schema_heads,
                                   source backends, per-file sha256 + size
  control_plane/config.db          SQLite online-backup API copy (consistent while live)
  warehouse/warehouse.duckdb       DuckDB file (+ warehouse.duckdb.wal when present)
  landing/<relative paths>         filesystem landing payloads (symlinks skipped)
```

- `schema_heads` records the latest migration per track (`sqlite`, `duckdb`, `postgres`, `postgres_run_metadata`) that the build creating the bundle ships.
- No settings values are written. That covers DSNs, S3 keys, HA tokens and passwords. The manifest records only backend names and the landing-root path. The SQLite control plane holds secret *references* (`auth_secret_name`/`auth_secret_key`) and password/token *hashes*, never plaintext secrets. Still treat the bundle as sensitive, because it contains household data.

### Create

Run from the same environment (same `HOMELAB_ANALYTICS_*` settings) as the instance:

```bash
python -m apps.worker.main backup /backups/homelab-$(date +%F)
```

- The destination must be new or empty. The command refuses to write into a non-empty directory.
- The SQLite control plane is captured consistently while the API and worker are running.
- The DuckDB warehouse is opened read-only during the copy. If another process holds the write lock, the command fails with `Stop worker and API processes that hold the warehouse before backing up`. Stop the worker (and API in warehouse mode), then rerun.
- The JSON output lists every component with `included` and, for excluded ones, `reason`.

### Verify

```bash
python -m apps.worker.main verify-backup /backups/homelab-2026-10-18
```

Exit code `0` means every file matches its recorded size and SHA-256, and the bundle's `schema_heads` match this build for each restorable component. Exit code `1` prints each problem: `Checksum mismatch for ...`, `Missing backup file: ...`, `Schema version mismatch for ...`, `Unsupported backup format_version ...`. Run `verify-backup` after copying a bundle off-host, and before every restore.

### Restore

1. Stop the API, the web app and the worker queue consumers.
2. Point the settings at the target data directory. Normally that is the original `HOMELAB_ANALYTICS_DATA_DIR`.
3. Restore:

```bash
python -m apps.worker.main restore /backups/homelab-2026-10-18
```

`restore` verifies the bundle first. It writes nothing when:

- any checksum, size, format-version or schema-head check fails. To restore across a schema change, use the release that created the bundle, restore with it, then upgrade.
- a target already holds data: a SQLite control plane with rows, a non-empty DuckDB file or WAL, or any file under `landing_root`.
- a component cannot be restored into the target backend. For example, a SQLite control-plane bundle into a Postgres-configured target, or filesystem landing into `blob_backend=s3`.

To deliberately replace an existing instance, add `--force`:

```bash
python -m apps.worker.main restore /backups/homelab-2026-10-18 --force
```

`--force` replaces the SQLite database (and removes its `-wal`/`-shm` sidecars) and the DuckDB file (and removes a stale WAL). It overwrites landing files that have the same relative path. Extra landing files that are not in the bundle stay in place. Files are copied to a temporary name and renamed into place.

**Landing path caveat:** run metadata stores *absolute* filesystem landing locators. Restore into the same `landing_root` path as the source, for example the same container mount. Otherwise payload reads for historical runs will not resolve. `restore` prints a `warning: Landing root differs ...` line when the paths differ.

4. Start the services and run the post-restore validation below.

### Drill (demo/dev, executable end to end)

```bash
export HOMELAB_ANALYTICS_DATA_DIR=$(mktemp -d)/source
python -m apps.worker.main ingest-account-transactions tests/fixtures/account_transactions_valid.csv
python -m apps.worker.main backup /tmp/ha-drill-backup
python -m apps.worker.main verify-backup /tmp/ha-drill-backup
HOMELAB_ANALYTICS_DATA_DIR=$(mktemp -d)/target python -m apps.worker.main restore /tmp/ha-drill-backup
```

`tests/test_worker_backup_restore.py` runs the same round trip in CI. It compares SQLite rows, DuckDB rows and landing bytes, and also covers the refusal paths.

## Shared Postgres deployments

### Postgres

The appservice deployment runs CNPG with a `pg_dump` CronJob. For a manual, schema-aware dump with a backup role that can read both schemas:

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

Keep a periodic portable snapshot of control-plane metadata for fast local recovery drills. It works on either backend:

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

If a worker or local-recovery workflow still depends on the warehouse PVC, run `python -m apps.worker.main backup <dir>` inside the worker pod while the worker loop is stopped, or snapshot the PVC.

### Restore (Postgres)

1. Stop worker queue consumers first.
2. Restore the Postgres schemas:

```bash
pg_restore \
  --clean \
  --if-exists \
  --no-owner \
  --dbname "$HOMELAB_ANALYTICS_CONTROL_PLANE_DSN" \
  /backups/homelab-control-2026-03-15.dump
```

3. Restore landed object data from the mirrored backup.
4. Restore the DuckDB warehouse with `worker restore` only if the recovery plan still depends on local warehouse state.
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
