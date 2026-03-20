"""Homelab domain transformation — load functions and mart builders.

Covers service health, backup freshness, storage risk, and workload cost.
All mart refreshes are full DELETE + INSERT (idempotent).

Cost model for workload_cost_7d:
    est_monthly_cost = (avg_cpu_pct / 100) * CPU_HOURLY_RATE * 730
                     + (avg_mem_gb)         * MEM_GB_HOURLY_RATE * 730
Rates are indicative defaults; override via config in a later sprint.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from packages.pipelines.homelab_models import (
    DIM_SERVICE,
    DIM_WORKLOAD,
    FACT_BACKUP_RUN_COLUMNS,
    FACT_BACKUP_RUN_TABLE,
    FACT_SERVICE_HEALTH_COLUMNS,
    FACT_SERVICE_HEALTH_TABLE,
    FACT_STORAGE_SENSOR_COLUMNS,
    FACT_STORAGE_SENSOR_TABLE,
    FACT_WORKLOAD_SENSOR_COLUMNS,
    FACT_WORKLOAD_SENSOR_TABLE,
    MART_BACKUP_FRESHNESS_COLUMNS,
    MART_BACKUP_FRESHNESS_TABLE,
    MART_SERVICE_HEALTH_CURRENT_COLUMNS,
    MART_SERVICE_HEALTH_CURRENT_TABLE,
    MART_STORAGE_RISK_COLUMNS,
    MART_STORAGE_RISK_TABLE,
    MART_WORKLOAD_COST_7D_COLUMNS,
    MART_WORKLOAD_COST_7D_TABLE,
    service_health_id,
    storage_sensor_id,
    workload_reading_id,
)
from packages.storage.duckdb_store import DuckDBStore

RecordLineage = Callable[..., None]

# Indicative cost rates (per hour) for the workload cost estimate.
_CPU_HOURLY_RATE = 0.02   # $ per 100% CPU-hour
_MEM_GB_HOURLY_RATE = 0.005  # $ per GB-hour
_HOURS_PER_MONTH = 730


def ensure_homelab_storage(store: DuckDBStore) -> None:
    store.ensure_table(FACT_SERVICE_HEALTH_TABLE, FACT_SERVICE_HEALTH_COLUMNS)
    store.ensure_table(FACT_BACKUP_RUN_TABLE, FACT_BACKUP_RUN_COLUMNS)
    store.ensure_table(FACT_STORAGE_SENSOR_TABLE, FACT_STORAGE_SENSOR_COLUMNS)
    store.ensure_table(FACT_WORKLOAD_SENSOR_TABLE, FACT_WORKLOAD_SENSOR_COLUMNS)
    store.ensure_table(MART_SERVICE_HEALTH_CURRENT_TABLE, MART_SERVICE_HEALTH_CURRENT_COLUMNS)
    store.ensure_table(MART_BACKUP_FRESHNESS_TABLE, MART_BACKUP_FRESHNESS_COLUMNS)
    store.ensure_table(MART_STORAGE_RISK_TABLE, MART_STORAGE_RISK_COLUMNS)
    store.ensure_table(MART_WORKLOAD_COST_7D_TABLE, MART_WORKLOAD_COST_7D_COLUMNS)


# ---------------------------------------------------------------------------
# Load functions
# ---------------------------------------------------------------------------

def load_service_health_rows(
    store: DuckDBStore,
    *,
    rows: list[dict[str, Any]],
    record_lineage: RecordLineage,
    run_id: str | None = None,
    source_system: str | None = None,
) -> int:
    if not rows:
        return 0

    fact_rows = []
    service_rows = []
    for row in rows:
        recorded_at = _coerce_ts(row["recorded_at"])
        service_id = str(row["service_id"])
        fact_rows.append(
            {
                "health_id": service_health_id(service_id, str(recorded_at)),
                "run_id": run_id,
                "service_id": service_id,
                "recorded_at": recorded_at,
                "state": str(row["state"]),
                "uptime_seconds": _opt_int(row.get("uptime_seconds")),
                "last_state_change": _opt_ts(row.get("last_state_change")),
            }
        )
        service_rows.append(
            {
                "service_id": service_id,
                "service_name": str(row.get("service_name", service_id)),
                "service_type": str(row.get("service_type", "unknown")),
                "host": str(row.get("host", "")),
                "criticality": str(row.get("criticality", "standard")),
                "managed_by": str(row.get("managed_by", "manual")),
            }
        )

    with store.atomic():
        svcs_upserted = store.upsert_dimension_rows(DIM_SERVICE, service_rows)
        inserted = store.insert_rows(FACT_SERVICE_HEALTH_TABLE, fact_rows)

    record_lineage(
        run_id=run_id,
        source_system=source_system,
        records=[
            ("dim_service", "dimension", svcs_upserted),
            (FACT_SERVICE_HEALTH_TABLE, "fact", inserted),
        ],
    )
    return inserted


def load_backup_run_rows(
    store: DuckDBStore,
    *,
    rows: list[dict[str, Any]],
    record_lineage: RecordLineage,
    run_id: str | None = None,
    source_system: str | None = None,
) -> int:
    if not rows:
        return 0

    fact_rows = []
    for row in rows:
        started_at = _coerce_ts(row["started_at"])
        completed_at = _opt_ts(row.get("completed_at"))
        duration_s = _opt_int(row.get("duration_s"))
        if duration_s is None and completed_at is not None:
            duration_s = int((completed_at - started_at).total_seconds())
        fact_rows.append(
            {
                "backup_id": str(row["backup_id"]),
                "run_id": run_id,
                "started_at": started_at,
                "completed_at": completed_at,
                "duration_s": duration_s,
                "size_bytes": _opt_int(row.get("size_bytes")),
                "target": str(row["target"]),
                "status": str(row["status"]),
            }
        )

    with store.atomic():
        inserted = store.insert_rows(FACT_BACKUP_RUN_TABLE, fact_rows)

    record_lineage(
        run_id=run_id,
        source_system=source_system,
        records=[(FACT_BACKUP_RUN_TABLE, "fact", inserted)],
    )
    return inserted


def load_storage_sensor_rows(
    store: DuckDBStore,
    *,
    rows: list[dict[str, Any]],
    record_lineage: RecordLineage,
    run_id: str | None = None,
    source_system: str | None = None,
) -> int:
    if not rows:
        return 0

    fact_rows = []
    for row in rows:
        entity_id = str(row["entity_id"])
        recorded_at = _coerce_ts(row["recorded_at"])
        fact_rows.append(
            {
                "sensor_id": storage_sensor_id(entity_id, str(recorded_at)),
                "run_id": run_id,
                "entity_id": entity_id,
                "device_name": str(row.get("device_name", entity_id)),
                "recorded_at": recorded_at,
                "capacity_bytes": int(row["capacity_bytes"]),
                "used_bytes": int(row["used_bytes"]),
                "sensor_type": row.get("sensor_type"),
            }
        )

    with store.atomic():
        inserted = store.insert_rows(FACT_STORAGE_SENSOR_TABLE, fact_rows)

    record_lineage(
        run_id=run_id,
        source_system=source_system,
        records=[(FACT_STORAGE_SENSOR_TABLE, "fact", inserted)],
    )
    return inserted


def load_workload_sensor_rows(
    store: DuckDBStore,
    *,
    rows: list[dict[str, Any]],
    record_lineage: RecordLineage,
    run_id: str | None = None,
    source_system: str | None = None,
) -> int:
    if not rows:
        return 0

    fact_rows = []
    workload_rows = []
    for row in rows:
        workload_id = str(row["workload_id"])
        entity_id = str(row.get("entity_id", workload_id))
        recorded_at = _coerce_ts(row["recorded_at"])
        fact_rows.append(
            {
                "reading_id": workload_reading_id(workload_id, str(recorded_at)),
                "run_id": run_id,
                "workload_id": workload_id,
                "entity_id": entity_id,
                "recorded_at": recorded_at,
                "cpu_pct": _opt_decimal(row.get("cpu_pct")),
                "mem_bytes": _opt_int(row.get("mem_bytes")),
            }
        )
        workload_rows.append(
            {
                "workload_id": workload_id,
                "entity_id": entity_id,
                "display_name": str(row.get("display_name", workload_id)),
                "host": str(row.get("host", "")),
                "workload_type": str(row.get("workload_type", "container")),
            }
        )

    with store.atomic():
        wl_upserted = store.upsert_dimension_rows(DIM_WORKLOAD, workload_rows)
        inserted = store.insert_rows(FACT_WORKLOAD_SENSOR_TABLE, fact_rows)

    record_lineage(
        run_id=run_id,
        source_system=source_system,
        records=[
            ("dim_workload", "dimension", wl_upserted),
            (FACT_WORKLOAD_SENSOR_TABLE, "fact", inserted),
        ],
    )
    return inserted


# ---------------------------------------------------------------------------
# Mart builders
# ---------------------------------------------------------------------------

def refresh_service_health_current(store: DuckDBStore) -> int:
    """Latest health record per service, joined with dim_service attributes."""
    store.execute(f"DELETE FROM {MART_SERVICE_HEALTH_CURRENT_TABLE}")
    store.execute(
        f"""
        INSERT INTO {MART_SERVICE_HEALTH_CURRENT_TABLE} (
            service_id, service_name, service_type, host, criticality, managed_by,
            state, uptime_seconds, last_state_change, recorded_at
        )
        WITH latest AS (
            SELECT
                service_id,
                MAX(recorded_at) AS max_recorded_at
            FROM {FACT_SERVICE_HEALTH_TABLE}
            GROUP BY service_id
        )
        SELECT
            h.service_id,
            d.service_name,
            d.service_type,
            d.host,
            d.criticality,
            d.managed_by,
            h.state,
            h.uptime_seconds,
            h.last_state_change,
            h.recorded_at
        FROM {FACT_SERVICE_HEALTH_TABLE} h
        JOIN latest l
            ON h.service_id = l.service_id
           AND h.recorded_at = l.max_recorded_at
        LEFT JOIN (
            SELECT
                service_id,
                ANY_VALUE(service_name)  AS service_name,
                ANY_VALUE(service_type)  AS service_type,
                ANY_VALUE(host)          AS host,
                ANY_VALUE(criticality)   AS criticality,
                ANY_VALUE(managed_by)    AS managed_by
            FROM dim_service
            GROUP BY service_id
        ) d ON d.service_id = h.service_id
        ORDER BY h.service_id
        """
    )
    return store.fetchall(
        f"SELECT COUNT(*) FROM {MART_SERVICE_HEALTH_CURRENT_TABLE}"
    )[0][0]


def refresh_backup_freshness(store: DuckDBStore) -> int:
    """Most recent *successful* backup per target with staleness flag (>24h = stale).

    Staleness is based on the last successful run only — failed retries do not
    mask a genuinely stale target.  status and size_bytes are taken from the
    same row as the MAX(started_at) so they are always correlated.
    """
    store.execute(f"DELETE FROM {MART_BACKUP_FRESHNESS_TABLE}")
    store.execute(
        f"""
        INSERT INTO {MART_BACKUP_FRESHNESS_TABLE} (
            target, last_backup_at, last_status, last_size_bytes,
            hours_since_backup, is_stale, backup_count_7d
        )
        WITH last_success_per_target AS (
            SELECT
                target,
                MAX(started_at) AS last_backup_at
            FROM {FACT_BACKUP_RUN_TABLE}
            WHERE status = 'success'
            GROUP BY target
        ),
        last_row AS (
            SELECT f.target, f.started_at AS last_backup_at, f.status AS last_status, f.size_bytes AS last_size_bytes
            FROM {FACT_BACKUP_RUN_TABLE} f
            JOIN last_success_per_target l
                ON f.target = l.target
               AND f.started_at = l.last_backup_at
               AND f.status = 'success'
        ),
        count_7d AS (
            SELECT
                target,
                COUNT(*) AS backup_count_7d
            FROM {FACT_BACKUP_RUN_TABLE}
            WHERE started_at >= CURRENT_TIMESTAMP - INTERVAL '7 days'
            GROUP BY target
        )
        SELECT
            l.target,
            l.last_backup_at,
            l.last_status,
            l.last_size_bytes,
            ROUND(
                CAST(epoch(CURRENT_TIMESTAMP) - epoch(l.last_backup_at) AS DECIMAL) / 3600.0,
                2
            )                                                   AS hours_since_backup,
            CASE
                WHEN l.last_backup_at IS NULL THEN TRUE
                WHEN (epoch(CURRENT_TIMESTAMP) - epoch(l.last_backup_at)) > 86400 THEN TRUE
                ELSE FALSE
            END                                                 AS is_stale,
            COALESCE(c.backup_count_7d, 0)                      AS backup_count_7d
        FROM last_row l
        LEFT JOIN count_7d c ON c.target = l.target
        ORDER BY l.target
        """
    )
    return store.fetchall(
        f"SELECT COUNT(*) FROM {MART_BACKUP_FRESHNESS_TABLE}"
    )[0][0]


def refresh_storage_risk(store: DuckDBStore) -> int:
    """Latest reading per device with risk tier: ok (<80%), warn (80-90%), crit (>90%)."""
    store.execute(f"DELETE FROM {MART_STORAGE_RISK_TABLE}")
    store.execute(
        f"""
        INSERT INTO {MART_STORAGE_RISK_TABLE} (
            entity_id, device_name, recorded_at,
            capacity_bytes, used_bytes, free_bytes, pct_used, risk_tier
        )
        WITH latest AS (
            SELECT
                entity_id,
                MAX(recorded_at) AS max_recorded_at
            FROM {FACT_STORAGE_SENSOR_TABLE}
            GROUP BY entity_id
        )
        SELECT
            s.entity_id,
            s.device_name,
            s.recorded_at,
            s.capacity_bytes,
            s.used_bytes,
            s.capacity_bytes - s.used_bytes                    AS free_bytes,
            ROUND(
                CAST(s.used_bytes AS DECIMAL) / s.capacity_bytes * 100.0,
                3
            )                                                  AS pct_used,
            CASE
                WHEN CAST(s.used_bytes AS DECIMAL) / s.capacity_bytes >= 0.9 THEN 'crit'
                WHEN CAST(s.used_bytes AS DECIMAL) / s.capacity_bytes >= 0.8 THEN 'warn'
                ELSE 'ok'
            END                                                AS risk_tier
        FROM {FACT_STORAGE_SENSOR_TABLE} s
        JOIN latest l
            ON s.entity_id = l.entity_id
           AND s.recorded_at = l.max_recorded_at
        ORDER BY pct_used DESC
        """
    )
    return store.fetchall(
        f"SELECT COUNT(*) FROM {MART_STORAGE_RISK_TABLE}"
    )[0][0]


def refresh_workload_cost_7d(store: DuckDBStore) -> int:
    """7-day rolling average CPU/mem per workload with indicative monthly cost estimate."""
    store.execute(f"DELETE FROM {MART_WORKLOAD_COST_7D_TABLE}")
    store.execute(
        f"""
        INSERT INTO {MART_WORKLOAD_COST_7D_TABLE} (
            workload_id, display_name, host, workload_type,
            avg_cpu_pct_7d, avg_mem_gb_7d, reading_count_7d, est_monthly_cost
        )
        WITH readings_7d AS (
            SELECT
                workload_id,
                AVG(cpu_pct)                                AS avg_cpu_pct,
                AVG(CAST(mem_bytes AS DECIMAL) / 1073741824) AS avg_mem_gb,
                COUNT(*)                                    AS reading_count
            FROM {FACT_WORKLOAD_SENSOR_TABLE}
            WHERE recorded_at >= CURRENT_TIMESTAMP - INTERVAL '7 days'
            GROUP BY workload_id
        ),
        dim AS (
            SELECT
                workload_id,
                ANY_VALUE(display_name) AS display_name,
                ANY_VALUE(host)         AS host,
                ANY_VALUE(workload_type) AS workload_type
            FROM dim_workload
            GROUP BY workload_id
        )
        SELECT
            r.workload_id,
            d.display_name,
            d.host,
            d.workload_type,
            ROUND(r.avg_cpu_pct, 3)   AS avg_cpu_pct_7d,
            ROUND(r.avg_mem_gb, 4)    AS avg_mem_gb_7d,
            r.reading_count           AS reading_count_7d,
            ROUND(
                (COALESCE(r.avg_cpu_pct, 0) / 100.0 * {_CPU_HOURLY_RATE} * {_HOURS_PER_MONTH})
                + (COALESCE(r.avg_mem_gb, 0) * {_MEM_GB_HOURLY_RATE} * {_HOURS_PER_MONTH}),
                4
            )                         AS est_monthly_cost
        FROM readings_7d r
        LEFT JOIN dim d ON d.workload_id = r.workload_id
        ORDER BY est_monthly_cost DESC NULLS LAST
        """
    )
    return store.fetchall(
        f"SELECT COUNT(*) FROM {MART_WORKLOAD_COST_7D_TABLE}"
    )[0][0]


# ---------------------------------------------------------------------------
# Query functions
# ---------------------------------------------------------------------------

def get_service_health_current(store: DuckDBStore) -> list[dict[str, Any]]:
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_SERVICE_HEALTH_CURRENT_TABLE} ORDER BY service_id"
    )


def get_backup_freshness(store: DuckDBStore) -> list[dict[str, Any]]:
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_BACKUP_FRESHNESS_TABLE} ORDER BY target"
    )


def get_storage_risk(store: DuckDBStore) -> list[dict[str, Any]]:
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_STORAGE_RISK_TABLE} ORDER BY pct_used DESC"
    )


def get_workload_cost_7d(store: DuckDBStore) -> list[dict[str, Any]]:
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_WORKLOAD_COST_7D_TABLE} ORDER BY est_monthly_cost DESC NULLS LAST"
    )


# ---------------------------------------------------------------------------
# Count helpers (used by tests)
# ---------------------------------------------------------------------------

def count_service_health_rows(store: DuckDBStore, *, run_id: str | None = None) -> int:
    if run_id is None:
        return store.fetchall(f"SELECT COUNT(*) FROM {FACT_SERVICE_HEALTH_TABLE}")[0][0]
    return store.fetchall(
        f"SELECT COUNT(*) FROM {FACT_SERVICE_HEALTH_TABLE} WHERE run_id = ?", [run_id]
    )[0][0]


def count_backup_run_rows(store: DuckDBStore, *, run_id: str | None = None) -> int:
    if run_id is None:
        return store.fetchall(f"SELECT COUNT(*) FROM {FACT_BACKUP_RUN_TABLE}")[0][0]
    return store.fetchall(
        f"SELECT COUNT(*) FROM {FACT_BACKUP_RUN_TABLE} WHERE run_id = ?", [run_id]
    )[0][0]


def count_storage_sensor_rows(store: DuckDBStore, *, run_id: str | None = None) -> int:
    if run_id is None:
        return store.fetchall(f"SELECT COUNT(*) FROM {FACT_STORAGE_SENSOR_TABLE}")[0][0]
    return store.fetchall(
        f"SELECT COUNT(*) FROM {FACT_STORAGE_SENSOR_TABLE} WHERE run_id = ?", [run_id]
    )[0][0]


def count_workload_sensor_rows(store: DuckDBStore, *, run_id: str | None = None) -> int:
    if run_id is None:
        return store.fetchall(f"SELECT COUNT(*) FROM {FACT_WORKLOAD_SENSOR_TABLE}")[0][0]
    return store.fetchall(
        f"SELECT COUNT(*) FROM {FACT_WORKLOAD_SENSOR_TABLE} WHERE run_id = ?", [run_id]
    )[0][0]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _coerce_ts(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _opt_ts(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    return _coerce_ts(value)


def _opt_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _opt_decimal(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)
