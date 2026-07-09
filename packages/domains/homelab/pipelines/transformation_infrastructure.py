from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from packages.domains.homelab.pipelines.infrastructure_models import (
    CURRENT_DIM_DEVICE_VIEW,
    CURRENT_DIM_NODE_VIEW,
    DIM_DEVICE,
    DIM_NODE,
    FACT_CLUSTER_METRIC_COLUMNS,
    FACT_CLUSTER_METRIC_TABLE,
    FACT_POWER_CONSUMPTION_COLUMNS,
    FACT_POWER_CONSUMPTION_TABLE,
    MART_CLUSTER_UTILIZATION_COLUMNS,
    MART_CLUSTER_UTILIZATION_TABLE,
    MART_INFRA_COST_COLUMNS,
    MART_INFRA_COST_TABLE,
    MART_UPTIME_SUMMARY_COLUMNS,
    MART_UPTIME_SUMMARY_TABLE,
    cluster_metric_id,
    power_consumption_id,
)
from packages.storage.duckdb_store import DuckDBStore

RecordLineage = Callable[..., None]

# Straight-line hardware amortisation window used by mart_infra_cost.
# Indicative default (three years); override via config in a later sprint.
_AMORTISATION_MONTHS = 36

# dim_asset.asset_type patterns that count as homelab/infrastructure hardware
# for the amortisation rows of mart_infra_cost.
_INFRA_ASSET_TYPE_PATTERNS = (
    "%server%",
    "%nas%",
    "%network%",
    "%router%",
    "%switch%",
    "%ups%",
    "%pdu%",
    "%homelab%",
    "%infra%",
    "%compute%",
)


def ensure_infrastructure_storage(store: DuckDBStore) -> None:
    store.ensure_dimension(DIM_NODE)
    store.ensure_dimension(DIM_DEVICE)
    store.ensure_current_dimension_view(DIM_NODE, CURRENT_DIM_NODE_VIEW)
    store.ensure_current_dimension_view(DIM_DEVICE, CURRENT_DIM_DEVICE_VIEW)
    store.ensure_table(FACT_CLUSTER_METRIC_TABLE, FACT_CLUSTER_METRIC_COLUMNS)
    store.ensure_table(FACT_POWER_CONSUMPTION_TABLE, FACT_POWER_CONSUMPTION_COLUMNS)
    store.ensure_table(MART_CLUSTER_UTILIZATION_TABLE, MART_CLUSTER_UTILIZATION_COLUMNS)
    store.ensure_table(MART_UPTIME_SUMMARY_TABLE, MART_UPTIME_SUMMARY_COLUMNS)
    store.ensure_table(MART_INFRA_COST_TABLE, MART_INFRA_COST_COLUMNS)


def load_cluster_metric_rows(
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
    node_rows = []
    for row in rows:
        recorded_at = _coerce_ts(row["recorded_at"])
        hostname = str(row["hostname"])
        metric_name = str(row["metric_name"])
        metric_value = _opt_decimal(row["metric_value"])
        if metric_value is None:
            raise ValueError("cluster metric rows must define metric_value")
        node_rows.append(
            {
                "hostname": hostname,
                "node_name": str(row.get("node_name", hostname)),
                "role": str(row.get("role", "unknown")),
                "cpu": str(row.get("cpu", "")),
                "ram_gb": _opt_decimal(row.get("ram_gb")),
                "os": str(row.get("os", "")),
            }
        )
        fact_rows.append(
            {
                "cluster_metric_id": cluster_metric_id(
                    hostname,
                    metric_name,
                    recorded_at.isoformat(),
                    metric_value,
                ),
                "run_id": run_id,
                "hostname": hostname,
                "node_name": str(row.get("node_name", hostname)),
                "recorded_at": recorded_at,
                "metric_name": metric_name,
                "metric_value": metric_value,
                "metric_unit": str(row.get("metric_unit", "")) or None,
                "source_system": source_system,
            }
        )

    with store.atomic():
        nodes_upserted = store.upsert_dimension_rows(
            DIM_NODE,
            node_rows,
            source_system=source_system,
            source_run_id=run_id,
        )
        inserted = store.insert_rows(FACT_CLUSTER_METRIC_TABLE, fact_rows)

    record_lineage(
        run_id=run_id,
        source_system=source_system,
        records=[
            ("dim_node", "dimension", nodes_upserted),
            (FACT_CLUSTER_METRIC_TABLE, "fact", inserted),
        ],
    )
    return inserted


def load_power_consumption_rows(
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
    device_rows = []
    for row in rows:
        recorded_at = _coerce_ts(row["recorded_at"])
        device_id = str(row["device_id"])
        watts = _opt_decimal(row["watts"])
        if watts is None:
            raise ValueError("power consumption rows must define watts")
        device_rows.append(
            {
                "device_id": device_id,
                "device_name": str(row.get("device_name", device_id)),
                "device_type": str(row.get("device_type", "unknown")),
                "location": str(row.get("location", "")),
                "power_rating_watts": _opt_decimal(row.get("power_rating_watts")),
            }
        )
        fact_rows.append(
            {
                "power_consumption_id": power_consumption_id(
                    device_id,
                    recorded_at.isoformat(),
                    watts,
                ),
                "run_id": run_id,
                "device_id": device_id,
                "device_name": str(row.get("device_name", device_id)),
                "recorded_at": recorded_at,
                "watts": watts,
                "source_system": source_system,
            }
        )

    with store.atomic():
        devices_upserted = store.upsert_dimension_rows(
            DIM_DEVICE,
            device_rows,
            source_system=source_system,
            source_run_id=run_id,
        )
        inserted = store.insert_rows(FACT_POWER_CONSUMPTION_TABLE, fact_rows)

    record_lineage(
        run_id=run_id,
        source_system=source_system,
        records=[
            ("dim_device", "dimension", devices_upserted),
            (FACT_POWER_CONSUMPTION_TABLE, "fact", inserted),
        ],
    )
    return inserted


def get_current_nodes(store: DuckDBStore) -> list[dict[str, Any]]:
    return store.fetchall_dicts(f"SELECT * FROM {CURRENT_DIM_NODE_VIEW} ORDER BY hostname")


def get_current_devices(store: DuckDBStore) -> list[dict[str, Any]]:
    return store.fetchall_dicts(f"SELECT * FROM {CURRENT_DIM_DEVICE_VIEW} ORDER BY device_id")


# ---------------------------------------------------------------------------
# Mart builders
# ---------------------------------------------------------------------------

def refresh_cluster_utilization(store: DuckDBStore) -> int:
    """Daily avg/max utilization per node, classified into resource types.

    ``metric_name`` is free-form (Prometheus federation lands raw metric
    names), so classification is pattern-based: cpu / memory / storage /
    other. The ``up`` availability metric feeds mart_uptime_summary instead
    and is excluded here.
    """
    store.execute(f"DELETE FROM {MART_CLUSTER_UTILIZATION_TABLE}")
    store.execute(
        f"""
        INSERT INTO {MART_CLUSTER_UTILIZATION_TABLE} (
            period_day, hostname, node_name, resource_type,
            avg_value, max_value, metric_unit, sample_count
        )
        WITH classified AS (
            SELECT
                CAST(recorded_at AS DATE)   AS period_day,
                hostname,
                node_name,
                CASE
                    WHEN LOWER(metric_name) LIKE '%cpu%'        THEN 'cpu'
                    WHEN LOWER(metric_name) LIKE '%mem%'        THEN 'memory'
                    WHEN LOWER(metric_name) LIKE '%disk%'
                      OR LOWER(metric_name) LIKE '%storage%'
                      OR LOWER(metric_name) LIKE '%filesystem%' THEN 'storage'
                    ELSE 'other'
                END                          AS resource_type,
                metric_value,
                metric_unit
            FROM {FACT_CLUSTER_METRIC_TABLE}
            WHERE LOWER(metric_name) <> 'up'
        )
        SELECT
            period_day,
            hostname,
            ANY_VALUE(node_name)             AS node_name,
            resource_type,
            ROUND(AVG(metric_value), 4)      AS avg_value,
            ROUND(MAX(metric_value), 4)      AS max_value,
            ANY_VALUE(metric_unit)           AS metric_unit,
            COUNT(*)                         AS sample_count
        FROM classified
        GROUP BY period_day, hostname, resource_type
        ORDER BY period_day, hostname, resource_type
        """
    )
    return store.fetchall(
        f"SELECT COUNT(*) FROM {MART_CLUSTER_UTILIZATION_TABLE}"
    )[0][0]


def refresh_uptime_summary(store: DuckDBStore) -> int:
    """Monthly availability percentage per node and per service.

    Nodes derive from the Prometheus ``up`` metric in fact_cluster_metric
    (value >= 1 counts as up). Services derive from fact_service_health
    (state = 'running' counts as up). Availability is sample-based — sparse
    scrape windows weight accordingly.
    """
    from packages.domains.homelab.pipelines.homelab_models import (
        FACT_SERVICE_HEALTH_TABLE,
    )

    store.execute(f"DELETE FROM {MART_UPTIME_SUMMARY_TABLE}")
    store.execute(
        f"""
        INSERT INTO {MART_UPTIME_SUMMARY_TABLE} (
            period_month, subject_type, subject_id, subject_name,
            availability_pct, up_samples, total_samples,
            first_observed_at, last_observed_at
        )
        SELECT
            strftime(recorded_at, '%Y-%m')                     AS period_month,
            'node'                                             AS subject_type,
            hostname                                           AS subject_id,
            ANY_VALUE(node_name)                               AS subject_name,
            ROUND(
                SUM(CASE WHEN metric_value >= 1 THEN 1 ELSE 0 END)
                    * 100.0 / COUNT(*),
                3
            )                                                  AS availability_pct,
            SUM(CASE WHEN metric_value >= 1 THEN 1 ELSE 0 END) AS up_samples,
            COUNT(*)                                           AS total_samples,
            MIN(recorded_at)                                   AS first_observed_at,
            MAX(recorded_at)                                   AS last_observed_at
        FROM {FACT_CLUSTER_METRIC_TABLE}
        WHERE LOWER(metric_name) = 'up'
        GROUP BY strftime(recorded_at, '%Y-%m'), hostname
        UNION ALL
        SELECT
            strftime(h.recorded_at, '%Y-%m')                   AS period_month,
            'service'                                          AS subject_type,
            h.service_id                                       AS subject_id,
            ANY_VALUE(d.service_name)                          AS subject_name,
            ROUND(
                SUM(CASE WHEN h.state = 'running' THEN 1 ELSE 0 END)
                    * 100.0 / COUNT(*),
                3
            )                                                  AS availability_pct,
            SUM(CASE WHEN h.state = 'running' THEN 1 ELSE 0 END) AS up_samples,
            COUNT(*)                                           AS total_samples,
            MIN(h.recorded_at)                                 AS first_observed_at,
            MAX(h.recorded_at)                                 AS last_observed_at
        FROM {FACT_SERVICE_HEALTH_TABLE} h
        LEFT JOIN (
            SELECT service_id, ANY_VALUE(service_name) AS service_name
            FROM dim_service
            GROUP BY service_id
        ) d ON d.service_id = h.service_id
        GROUP BY strftime(h.recorded_at, '%Y-%m'), h.service_id
        ORDER BY period_month, subject_type, subject_id
        """
    )
    return store.fetchall(
        f"SELECT COUNT(*) FROM {MART_UPTIME_SUMMARY_TABLE}"
    )[0][0]


def refresh_infra_cost(store: DuckDBStore) -> int:
    """Monthly infrastructure cost: metered electricity plus hardware amortisation.

    Electricity rows estimate kWh per device-month from the average sampled
    power draw (avg watts x 24h x days in month / 1000) and price it with the
    most recently valid active per-kWh component from
    mart_electricity_price_current when one exists; otherwise est_cost is
    NULL and cost_basis records that no tariff was available.

    Hardware rows straight-line acquisition events for infrastructure-typed
    assets over ``_AMORTISATION_MONTHS``, up to the current month.
    """
    from packages.domains.finance.pipelines.asset_models import (
        CURRENT_DIM_ASSET_VIEW,
    )
    from packages.domains.finance.pipelines.contract_price_models import (
        MART_ELECTRICITY_PRICE_CURRENT_TABLE,
    )

    asset_type_filter = " OR ".join(
        f"LOWER(a.asset_type) LIKE '{pattern}'"
        for pattern in _INFRA_ASSET_TYPE_PATTERNS
    )

    store.execute(f"DELETE FROM {MART_INFRA_COST_TABLE}")
    store.execute(
        f"""
        INSERT INTO {MART_INFRA_COST_TABLE} (
            billing_month, cost_type, subject_id, subject_name,
            est_kwh, unit_price, currency, est_cost, cost_basis
        )
        WITH tariff AS (
            SELECT unit_price, currency
            FROM {MART_ELECTRICITY_PRICE_CURRENT_TABLE}
            WHERE status = 'active'
              AND LOWER(COALESCE(quantity_unit, '')) LIKE '%kwh%'
            ORDER BY valid_from DESC
            LIMIT 1
        ),
        monthly_power AS (
            SELECT
                strftime(recorded_at, '%Y-%m')             AS billing_month,
                date_trunc('month', MIN(recorded_at))      AS month_start,
                device_id,
                ANY_VALUE(device_name)                     AS device_name,
                AVG(watts)                                 AS avg_watts
            FROM {FACT_POWER_CONSUMPTION_TABLE}
            GROUP BY strftime(recorded_at, '%Y-%m'), device_id
        ),
        electricity AS (
            SELECT
                p.billing_month,
                'electricity'                              AS cost_type,
                p.device_id                                AS subject_id,
                p.device_name                              AS subject_name,
                ROUND(
                    p.avg_watts * 24
                        * date_diff(
                            'day',
                            CAST(p.month_start AS DATE),
                            CAST(p.month_start + INTERVAL 1 MONTH AS DATE)
                        )
                        / 1000.0,
                    4
                )                                          AS est_kwh,
                t.unit_price,
                t.currency,
                CASE
                    WHEN t.unit_price IS NOT NULL THEN ROUND(
                        p.avg_watts * 24
                            * date_diff(
                                'day',
                                CAST(p.month_start AS DATE),
                                CAST(p.month_start + INTERVAL 1 MONTH AS DATE)
                            )
                            / 1000.0 * t.unit_price,
                        4
                    )
                    ELSE NULL
                END                                        AS est_cost,
                CASE
                    WHEN t.unit_price IS NOT NULL THEN 'metered_power_x_tariff'
                    ELSE 'metered_power_no_tariff'
                END                                        AS cost_basis
            FROM monthly_power p
            LEFT JOIN tariff t ON TRUE
        ),
        infra_acquisitions AS (
            SELECT
                e.asset_id,
                e.asset_name,
                date_trunc('month', e.event_date)          AS acquired_month,
                e.amount,
                e.currency
            FROM fact_asset_event e
            JOIN {CURRENT_DIM_ASSET_VIEW} a ON a.asset_id = e.asset_id
            WHERE e.event_type = 'acquisition'
              AND ({asset_type_filter})
        ),
        amortisation AS (
            SELECT
                strftime(
                    q.acquired_month + to_months(CAST(gs.offs AS INTEGER)),
                    '%Y-%m'
                )                                          AS billing_month,
                'hardware_amortisation'                    AS cost_type,
                q.asset_id                                 AS subject_id,
                q.asset_name                               AS subject_name,
                CAST(NULL AS DECIMAL(18,4))                AS est_kwh,
                CAST(NULL AS DECIMAL(18,4))                AS unit_price,
                q.currency,
                ROUND(q.amount / {_AMORTISATION_MONTHS}, 4) AS est_cost,
                'straight_line_{_AMORTISATION_MONTHS}m'    AS cost_basis
            FROM infra_acquisitions q
            CROSS JOIN generate_series(0, {_AMORTISATION_MONTHS - 1}) AS gs(offs)
            WHERE q.acquired_month + to_months(CAST(gs.offs AS INTEGER))
                <= date_trunc('month', CURRENT_DATE)
        )
        SELECT * FROM electricity
        UNION ALL
        SELECT * FROM amortisation
        ORDER BY billing_month, cost_type, subject_id
        """
    )
    return store.fetchall(
        f"SELECT COUNT(*) FROM {MART_INFRA_COST_TABLE}"
    )[0][0]


def get_cluster_utilization(
    store: DuckDBStore,
    *,
    hostname: str | None = None,
    resource_type: str | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if hostname is not None:
        clauses.append("hostname = ?")
        params.append(hostname)
    if resource_type is not None:
        clauses.append("resource_type = ?")
        params.append(resource_type)
    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_CLUSTER_UTILIZATION_TABLE}"
        f" {where_sql} ORDER BY period_day, hostname, resource_type",
        params,
    )


def get_uptime_summary(
    store: DuckDBStore,
    *,
    subject_type: str | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if subject_type is not None:
        clauses.append("subject_type = ?")
        params.append(subject_type)
    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_UPTIME_SUMMARY_TABLE}"
        f" {where_sql} ORDER BY period_month, subject_type, subject_id",
        params,
    )


def get_infra_cost(
    store: DuckDBStore,
    *,
    cost_type: str | None = None,
    billing_month: str | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if cost_type is not None:
        clauses.append("cost_type = ?")
        params.append(cost_type)
    if billing_month is not None:
        clauses.append("billing_month = ?")
        params.append(billing_month)
    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_INFRA_COST_TABLE}"
        f" {where_sql} ORDER BY billing_month, cost_type, subject_id",
        params,
    )


def count_cluster_metric_rows(store: DuckDBStore, *, run_id: str | None = None) -> int:
    if run_id is None:
        return store.fetchall(f"SELECT COUNT(*) FROM {FACT_CLUSTER_METRIC_TABLE}")[0][0]
    return store.fetchall(
        f"SELECT COUNT(*) FROM {FACT_CLUSTER_METRIC_TABLE} WHERE run_id = ?",
        [run_id],
    )[0][0]


def count_power_consumption_rows(store: DuckDBStore, *, run_id: str | None = None) -> int:
    if run_id is None:
        return store.fetchall(f"SELECT COUNT(*) FROM {FACT_POWER_CONSUMPTION_TABLE}")[0][0]
    return store.fetchall(
        f"SELECT COUNT(*) FROM {FACT_POWER_CONSUMPTION_TABLE} WHERE run_id = ?",
        [run_id],
    )[0][0]


def _coerce_ts(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _opt_decimal(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)
