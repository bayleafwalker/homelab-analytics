# Backup And Restore

## Scope

State lives in four places. Which tool backs each one up depends on the backend:

| Store | SQLite / filesystem deployments (single-user Compose, demo/dev) | Shared Postgres deployments (appservice) |
|---|---|---|
| Control plane + run metadata | `worker backup` (SQLite `config.db`) | `pg_dump` of the `control` schema (CNPG backup CronJob) |
| Reporting marts | `worker backup` (DuckDB warehouse) | `pg_dump` of the `reporting` schema |
| DuckDB warehouse (transformation + reporting) | `worker backup` | Worker-loop scheduled backup + off-site shipping ([below](#scheduled-backups-running-worker)) |
| Landed payloads | `worker backup` (filesystem `landing_root`) | Filesystem landing (first rollout): scheduled backup. Object storage: bucket mirror (`aws s3 sync` / `mc mirror`) |

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
- The DuckDB warehouse is opened read-only during the copy. A lock conflict is retried with backoff (about 7.5 s); if a writer holds the lock throughout, the command fails with `Stop worker and API processes that hold the warehouse`. Stop the long-running writer, then rerun — or let the running worker take the backup itself ([scheduled backups](#scheduled-backups-running-worker)).
- Landing payloads are written atomically (temporary `.partial` name, then rename), and backups skip `.partial` files, so a bundle never captures a half-written payload.
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

## API warehouse access

DuckDB admits one read-write process per file, or any number of read-only ones. The API therefore never keeps the warehouse open:

- Reads (`get_*`, `count_*`, `list_*` and store `fetchall*`/`query_*`) run on a **read-only** handle. Read-only handles coexist with the backup's read-only guard in another process. The few read-named facet methods that still issue schema DDL before reading (HA entity reads, scenario reads; `READ_NAMED_WRITE_METHODS` in `packages/pipelines/warehouse_session.py`) take a read-write handle; a test scans every `TransformationService` facet method so new ones cannot slip through unclassified.
- Writes (promotion after an upload or run retry, category edits, scenario create/archive, HA state ingest) open a **read-write** handle for the duration of the call.
- The handle is closed when the last in-flight request finishes, or after `HOMELAB_ANALYTICS_API_WAREHOUSE_IDLE_SECONDS` (default 5) for background callers such as the HA bridge.
- Opening while another process holds the write lock is retried (`HOMELAB_ANALYTICS_WAREHOUSE_LOCK_RETRY_ATTEMPTS`, default 4, backoff from `..._BACKOFF_SECONDS` = 0.1 doubling). If the lock is still held, the request returns **503** with `Retry-After: 5` instead of a 500.
- `homelab_analytics_api_warehouse_handle_open{mode="read_only"|"read_write"}` is 1 while the API holds a handle; `..._busy_total` counts 503s from lock conflicts.

The worker also retries lock conflicts when it opens the warehouse for a promotion (6 attempts, about 3 s), so a short API session never fails a dispatch.

`tests/test_api_warehouse_sessions.py` shows that, after an API read, another process can open the warehouse read-only and read-write; that a scheduled backup in another process succeeds while the API serves reads; and that a held write lock produces 503, then 200 once it is released.

## Scheduled backups (running worker)

A one-off `worker backup` cannot run beside the long-running worker: the DuckDB warehouse admits one writer process, and the read-only capture is refused while a writer holds the lock. The worker therefore owns the schedule itself.

**How it stays consistent**

1. `watch-schedule-dispatches` checks the schedule at its *idle yield point*: an iteration that claimed no dispatch. Dispatch processing is synchronous on the loop thread, so none of this worker's ingestion or promotion can be in flight.
2. Every promotion closes its DuckDB connection before returning, so at that point the worker process holds no warehouse handle.
3. `create_backup` opens the warehouse read-only. DuckDB refuses that while another process holds the write lock, and while the read-only handle is open no writer can attach — the file and its WAL are quiescent for the copy. The API never keeps a write handle: it reads through short-lived read-only handles (which coexist with the backup's) and opens read-write only for the duration of a write ([API warehouse access](#api-warehouse-access)). A lock conflict is retried inside the same idle window (5 attempts, 0.5 s doubling, about 7.5 s); only if a writer holds the lock throughout is the attempt recorded as a failure and retried after `min(interval, 15 min)`. Ingestion is never blocked or interrupted.
4. The control plane (SQLite) is captured with the online-backup API; Postgres stores are excluded (pg_dump covers them).
5. The bundle is staged as `.staging-<stamp>-<id>/`, verified with `verify_backup` (checksums + schema heads), then atomically renamed to `backup-<UTC stamp>/`. Only then are bundles beyond the retention count pruned (oldest first). An advisory lock (`.backup.lock`) prevents two schedulers from running at once.
6. The outcome goes to `backup-status.json` (`last_success_at`, `last_error`, `consecutive_failures`, sizes). The API and the worker export it as `homelab_analytics_backup_*` metrics; see [slo.md](slo.md).

`tests/test_scheduled_backup.py` proves this: a writer in another process is refused while the warehouse is copied, a process holding the write lock makes the backup fail cleanly and the retry succeed with the holder's write intact, a worker loop processes a dispatch, backs up while idle, restores into scratch with identical warehouse row counts and landing files, and then ingests again.

**Configure** (worker container; see [configuration.md](configuration.md)):

| Variable | Example | Meaning |
|---|---|---|
| `HOMELAB_ANALYTICS_BACKUP_INTERVAL_SECONDS` | `86400` | Daily; `0` (default) disables |
| `HOMELAB_ANALYTICS_BACKUP_RETENTION_COUNT` | `7` | Local bundles kept |
| `HOMELAB_ANALYTICS_BACKUP_DIR` | `/data/backups` | Default `<data_dir>/backups`; must be outside the landing root |

```text
/data/backups/
  backup-20261018T030012Z/     complete, verified bundle (safe to ship)
  backup-20261019T030009Z/
  .staging-...                 in progress; never ship
  backup-status.json           last attempt / success / failure
  restore-drill-status.json    last drill receipt
```

The local bundles share the PVC with the data, so they protect against corruption and bad releases, not volume loss. Ship them off-site: the appservice proposal adds a `backup-ship` sidecar that streams each new `backup-*` directory as `tar | age | rclone rcat` to the same Object-Lock bucket and recipients as `cnpg-pgdump-age` ([proposal](../notes/appservice-proposals/README.md)).

One-off run with the same staging, verification, retention and status path (operator, drill prep):

```bash
python -m apps.worker.main scheduled-backup            # uses HOMELAB_ANALYTICS_BACKUP_DIR
python -m apps.worker.main scheduled-backup --backup-dir /tmp/bundles
```

It is subject to the same warehouse lock as `worker backup`: inside the running pod, prefer letting the loop take it.

## Restore drill

`restore-drill` restores a bundle — by default the newest `backup-*` under the backup directory — into an empty scratch directory, never the live stores. It verifies checksums and schema heads, restores every included component, scans every warehouse table, and checks the restored landing tree against the manifest. The receipt is printed and written to `restore-drill-status.json` (exported as `homelab_analytics_backup_restore_drill_*`).

```bash
# Inside the worker container (or any host with the bundle and the same release):
python -m apps.worker.main restore-drill
python -m apps.worker.main restore-drill --bundle /data/backups/backup-20261018T030012Z --keep-scratch --scratch-dir /tmp/drill
scripts/restore-drill.sh                # wrapper: drill + one-line summary, non-zero on failure
```

Exit code `0` and `"passed": true` mean the bundle is restorable with this release. Run it weekly (the `RestoreDrillStale` alert fires after 8 days) and after every release that changes a DuckDB migration. For an off-site copy, first fetch and decrypt it (`rclone cat ... | age -d -i <identity> | tar -x -C /tmp/fetched`), then `restore-drill --backup-dir /tmp/fetched`.

## CNPG restore drill outline

The Postgres side (control plane, run metadata, reporting) is restored from the hourly `cnpg-pgdump-age` objects (`<cluster>-<db>-<UTC stamp>.dump.age` under `backups/pgdump-age/analytics/analytics-postgres/`). The estate's `cnpg-dump-drill` namespace already restores dumps daily for the clusters it covers; for homelab-analytics the drill must additionally prove the application can run on the restored data:

1. **Pick the dump**: newest `analytics-postgres-homelab_analytics-*.dump.age`; record its stamp (RPO evidence: age of the dump at incident time, target <= 1 h).
2. **Scratch database**: create a throwaway CNPG `Cluster` (or a plain `postgres:16` pod) in the drill namespace; never the live `analytics-postgres`.
3. **Restore**: `rclone cat <object> | age -d -i <drill identity> | pg_restore --no-owner --dbname <scratch DSN>`. The drill identity is the `pgdump-drill` recipient already used by `cnpg-pgdump-age`.
4. **Schema check**: confirm the restored `schema_migrations` versions in the control schema reach the `postgres` and `postgres_run_metadata` heads this release ships (`packages.storage.backup_bundle.current_schema_heads()`); running the deployment's `migrate` initContainer against the scratch DSN must apply nothing.
5. **App check**: run the release image against the scratch DSN with a scratch `/data`: `homelab-analytics-worker list-runs`, `list-schedule-dispatches`, `list-worker-heartbeats`; start the API and require `/ready` = 200 and one publication endpoint returning rows.
6. **Pair with the warehouse drill**: run `restore-drill` on the bundle closest in time to the dump, so Postgres and DuckDB/landing restore together (the RPO between them is the backup interval).
7. **Record**: dump stamp, bundle name, durations (RTO evidence), pass/fail into the drill log; delete the scratch database.

Automating steps 2-5 as a CronJob in `cnpg-dump-drill` is follow-up work for the cluster repo.

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

Enable the worker-loop schedule ([scheduled backups](#scheduled-backups-running-worker)) so the running worker captures the warehouse and filesystem landing itself, and ship the bundles off-site. Without it, run `python -m apps.worker.main backup <dir>` inside the worker pod while the worker loop is stopped, or snapshot the PVC.

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
