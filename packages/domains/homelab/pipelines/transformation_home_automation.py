from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from packages.domains.homelab.pipelines.home_automation_models import (
    CURRENT_DIM_ENTITY_VIEW,
    DIM_ENTITY,
    FACT_AUTOMATION_EVENT_COLUMNS,
    FACT_AUTOMATION_EVENT_TABLE,
    FACT_SENSOR_READING_COLUMNS,
    FACT_SENSOR_READING_TABLE,
    MART_AUTOMATION_RELIABILITY_COLUMNS,
    MART_AUTOMATION_RELIABILITY_TABLE,
    MART_CLIMATE_SUMMARY_COLUMNS,
    MART_CLIMATE_SUMMARY_TABLE,
    MART_DEVICE_BATTERY_COLUMNS,
    MART_DEVICE_BATTERY_TABLE,
)
from packages.domains.homelab.pipelines.home_automation_models import (
    count_automation_event_rows as _count_automation_event_rows,
)
from packages.domains.homelab.pipelines.home_automation_models import (
    count_home_automation_state_rows as _count_home_automation_state_rows,
)
from packages.domains.homelab.pipelines.home_automation_models import (
    count_sensor_reading_rows as _count_sensor_reading_rows,
)
from packages.domains.homelab.pipelines.home_automation_models import (
    get_current_entities as _get_current_entities,
)
from packages.domains.homelab.pipelines.home_automation_models import (
    load_automation_events as _load_automation_events,
)
from packages.domains.homelab.pipelines.home_automation_models import (
    load_home_automation_state_rows as _load_home_automation_state_rows,
)
from packages.domains.homelab.pipelines.home_automation_models import (
    load_sensor_readings as _load_sensor_readings,
)
from packages.storage.duckdb_store import DuckDBStore

RecordLineage = Callable[..., None]


def ensure_home_automation_storage(store: DuckDBStore) -> None:
    store.ensure_dimension(DIM_ENTITY)
    store.ensure_current_dimension_view(DIM_ENTITY, CURRENT_DIM_ENTITY_VIEW)
    store.ensure_table(FACT_SENSOR_READING_TABLE, FACT_SENSOR_READING_COLUMNS)
    store.ensure_table(FACT_AUTOMATION_EVENT_TABLE, FACT_AUTOMATION_EVENT_COLUMNS)
    store.ensure_table(MART_CLIMATE_SUMMARY_TABLE, MART_CLIMATE_SUMMARY_COLUMNS)
    store.ensure_table(
        MART_AUTOMATION_RELIABILITY_TABLE, MART_AUTOMATION_RELIABILITY_COLUMNS
    )
    store.ensure_table(MART_DEVICE_BATTERY_TABLE, MART_DEVICE_BATTERY_COLUMNS)


def load_home_automation_state_rows(
    store: DuckDBStore,
    *,
    rows: list[dict[str, Any]],
    record_lineage: RecordLineage,
    run_id: str | None = None,
    effective_date: date | None = None,
    source_system: str | None = None,
) -> int:
    return _load_home_automation_state_rows(
        store,
        rows=rows,
        record_lineage=record_lineage,
        run_id=run_id,
        effective_date=effective_date,
        source_system=source_system,
    )


def load_sensor_readings(
    store: DuckDBStore,
    *,
    rows: list[dict[str, Any]],
    record_lineage: RecordLineage,
    run_id: str | None = None,
    effective_date: date | None = None,
    source_system: str | None = None,
) -> int:
    return _load_sensor_readings(
        store,
        rows=rows,
        record_lineage=record_lineage,
        run_id=run_id,
        effective_date=effective_date,
        source_system=source_system,
    )


def load_automation_events(
    store: DuckDBStore,
    *,
    rows: list[dict[str, Any]],
    record_lineage: RecordLineage,
    run_id: str | None = None,
    effective_date: date | None = None,
    source_system: str | None = None,
) -> int:
    return _load_automation_events(
        store,
        rows=rows,
        record_lineage=record_lineage,
        run_id=run_id,
        effective_date=effective_date,
        source_system=source_system,
    )


# ---------------------------------------------------------------------------
# Mart builders
# ---------------------------------------------------------------------------

# Automation results that count as failures for mart_automation_reliability.
_FAILURE_RESULTS = ("failed", "failure", "error", "timeout", "unavailable")

# Battery level thresholds for mart_device_battery status tiers.
_BATTERY_LOW_PCT = 25
_BATTERY_CRITICAL_PCT = 10


def refresh_climate_summary(store: DuckDBStore) -> int:
    """Daily indoor temperature/humidity aggregates per area.

    Sensor states are free-form strings, so only numeric readings are used
    (TRY_CAST). Measures are classified from the entity id or unit; entities
    without an area group under 'unassigned'.
    """
    store.execute(f"DELETE FROM {MART_CLIMATE_SUMMARY_TABLE}")
    store.execute(
        f"""
        INSERT INTO {MART_CLIMATE_SUMMARY_TABLE} (
            period_day, area, measure, avg_value, min_value, max_value,
            unit, reading_count
        )
        WITH readings AS (
            SELECT
                CAST(r.recorded_at AS DATE)          AS period_day,
                COALESCE(e.area, 'unassigned')       AS area,
                CASE
                    WHEN LOWER(r.entity_id) LIKE '%temperature%'
                      OR LOWER(COALESCE(r.unit, '')) IN ('°c', 'c', '°f', 'f')
                        THEN 'temperature'
                    WHEN LOWER(r.entity_id) LIKE '%humidity%'
                        THEN 'humidity'
                    ELSE NULL
                END                                  AS measure,
                TRY_CAST(r.state AS DECIMAL(18,4))   AS reading_value,
                r.unit
            FROM {FACT_SENSOR_READING_TABLE} r
            LEFT JOIN {CURRENT_DIM_ENTITY_VIEW} e ON e.entity_id = r.entity_id
        )
        SELECT
            period_day,
            area,
            measure,
            ROUND(AVG(reading_value), 4)   AS avg_value,
            ROUND(MIN(reading_value), 4)   AS min_value,
            ROUND(MAX(reading_value), 4)   AS max_value,
            ANY_VALUE(unit)                AS unit,
            COUNT(*)                       AS reading_count
        FROM readings
        WHERE measure IS NOT NULL
          AND reading_value IS NOT NULL
        GROUP BY period_day, area, measure
        ORDER BY period_day, area, measure
        """
    )
    return store.fetchall(
        f"SELECT COUNT(*) FROM {MART_CLIMATE_SUMMARY_TABLE}"
    )[0][0]


def refresh_automation_reliability(store: DuckDBStore) -> int:
    """Monthly success/failure rates per automation entity.

    An event counts as a failure when its result matches a known failure
    token; everything else counts as success (HA reports plain state values
    like 'on' for successful runs).
    """
    failure_list = ", ".join(f"'{result}'" for result in _FAILURE_RESULTS)
    store.execute(f"DELETE FROM {MART_AUTOMATION_RELIABILITY_TABLE}")
    store.execute(
        f"""
        INSERT INTO {MART_AUTOMATION_RELIABILITY_TABLE} (
            period_month, entity_id, entity_name, run_count,
            success_count, failure_count, success_rate_pct,
            last_run_at, last_result
        )
        WITH events AS (
            SELECT
                strftime(recorded_at, '%Y-%m')  AS period_month,
                entity_id,
                entity_name,
                recorded_at,
                result,
                CASE
                    WHEN LOWER(COALESCE(result, '')) IN ({failure_list})
                      OR LOWER(COALESCE(result, '')) LIKE '%error%'
                      OR LOWER(COALESCE(result, '')) LIKE '%fail%'
                        THEN 0
                    ELSE 1
                END                             AS is_success
            FROM {FACT_AUTOMATION_EVENT_TABLE}
        )
        SELECT
            period_month,
            entity_id,
            ANY_VALUE(entity_name)                             AS entity_name,
            COUNT(*)                                           AS run_count,
            SUM(is_success)                                    AS success_count,
            COUNT(*) - SUM(is_success)                         AS failure_count,
            ROUND(SUM(is_success) * 100.0 / COUNT(*), 3)       AS success_rate_pct,
            MAX(recorded_at)                                   AS last_run_at,
            ARG_MAX(result, recorded_at)                       AS last_result
        FROM events
        GROUP BY period_month, entity_id
        ORDER BY period_month, entity_id
        """
    )
    return store.fetchall(
        f"SELECT COUNT(*) FROM {MART_AUTOMATION_RELIABILITY_TABLE}"
    )[0][0]


def refresh_device_battery(store: DuckDBStore) -> int:
    """Latest battery level per battery entity with a linear drain estimate.

    Drain is estimated from the first and last numeric reading; the
    days-to-empty projection only exists when at least two readings span a
    positive time window with a net decline.
    """
    store.execute(f"DELETE FROM {MART_DEVICE_BATTERY_TABLE}")
    store.execute(
        f"""
        INSERT INTO {MART_DEVICE_BATTERY_TABLE} (
            entity_id, entity_name, device_name, area, battery_pct,
            recorded_at, avg_daily_drain_pct, est_days_to_empty, battery_status
        )
        WITH battery AS (
            SELECT
                entity_id,
                entity_name,
                recorded_at,
                TRY_CAST(state AS DECIMAL(18,4)) AS battery_value
            FROM {FACT_SENSOR_READING_TABLE}
            WHERE (
                LOWER(entity_id) LIKE '%battery%'
                OR LOWER(entity_name) LIKE '%battery%'
            )
              AND TRY_CAST(state AS DECIMAL(18,4)) IS NOT NULL
        ),
        stats AS (
            SELECT
                entity_id,
                ANY_VALUE(entity_name)                     AS entity_name,
                MAX(recorded_at)                           AS last_at,
                MIN(recorded_at)                           AS first_at,
                ARG_MAX(battery_value, recorded_at)        AS last_pct,
                ARG_MIN(battery_value, recorded_at)        AS first_pct
            FROM battery
            GROUP BY entity_id
        ),
        derived AS (
            SELECT
                *,
                (epoch(last_at) - epoch(first_at)) / 86400.0 AS span_days
            FROM stats
        )
        SELECT
            d.entity_id,
            d.entity_name,
            e.device_name,
            e.area,
            d.last_pct                                     AS battery_pct,
            d.last_at                                      AS recorded_at,
            CASE
                WHEN d.span_days > 0 AND d.first_pct > d.last_pct
                    THEN ROUND((d.first_pct - d.last_pct) / d.span_days, 4)
                ELSE NULL
            END                                            AS avg_daily_drain_pct,
            CASE
                WHEN d.span_days > 0 AND d.first_pct > d.last_pct
                    THEN CAST(FLOOR(
                        d.last_pct / ((d.first_pct - d.last_pct) / d.span_days)
                    ) AS INTEGER)
                ELSE NULL
            END                                            AS est_days_to_empty,
            CASE
                WHEN d.last_pct < {_BATTERY_CRITICAL_PCT} THEN 'critical'
                WHEN d.last_pct < {_BATTERY_LOW_PCT}      THEN 'low'
                ELSE 'ok'
            END                                            AS battery_status
        FROM derived d
        LEFT JOIN {CURRENT_DIM_ENTITY_VIEW} e ON e.entity_id = d.entity_id
        ORDER BY battery_pct, d.entity_id
        """
    )
    return store.fetchall(
        f"SELECT COUNT(*) FROM {MART_DEVICE_BATTERY_TABLE}"
    )[0][0]


def get_climate_summary(
    store: DuckDBStore,
    *,
    area: str | None = None,
    measure: str | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if area is not None:
        clauses.append("area = ?")
        params.append(area)
    if measure is not None:
        clauses.append("measure = ?")
        params.append(measure)
    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_CLIMATE_SUMMARY_TABLE}"
        f" {where_sql} ORDER BY period_day, area, measure",
        params,
    )


def get_automation_reliability(
    store: DuckDBStore,
    *,
    entity_id: str | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if entity_id is not None:
        clauses.append("entity_id = ?")
        params.append(entity_id)
    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_AUTOMATION_RELIABILITY_TABLE}"
        f" {where_sql} ORDER BY period_month, entity_id",
        params,
    )


def get_device_battery(
    store: DuckDBStore,
    *,
    battery_status: str | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if battery_status is not None:
        clauses.append("battery_status = ?")
        params.append(battery_status)
    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_DEVICE_BATTERY_TABLE}"
        f" {where_sql} ORDER BY battery_pct, entity_id",
        params,
    )


def get_current_entities(store: DuckDBStore) -> list[dict[str, Any]]:
    return _get_current_entities(store)


def count_sensor_reading_rows(store: DuckDBStore, *, run_id: str | None = None) -> int:
    return _count_sensor_reading_rows(store, run_id=run_id)


def count_automation_event_rows(store: DuckDBStore, *, run_id: str | None = None) -> int:
    return _count_automation_event_rows(store, run_id=run_id)


def count_home_automation_state_rows(store: DuckDBStore, *, run_id: str | None = None) -> int:
    return _count_home_automation_state_rows(store, run_id=run_id)
