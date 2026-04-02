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
    cluster_metric_id,
    power_consumption_id,
)
from packages.storage.duckdb_store import DuckDBStore

RecordLineage = Callable[..., None]


def ensure_infrastructure_storage(store: DuckDBStore) -> None:
    store.ensure_dimension(DIM_NODE)
    store.ensure_dimension(DIM_DEVICE)
    store.ensure_current_dimension_view(DIM_NODE, CURRENT_DIM_NODE_VIEW)
    store.ensure_current_dimension_view(DIM_DEVICE, CURRENT_DIM_DEVICE_VIEW)
    store.ensure_table(FACT_CLUSTER_METRIC_TABLE, FACT_CLUSTER_METRIC_COLUMNS)
    store.ensure_table(FACT_POWER_CONSUMPTION_TABLE, FACT_POWER_CONSUMPTION_COLUMNS)


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
