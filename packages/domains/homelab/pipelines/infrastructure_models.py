from __future__ import annotations

import hashlib

from packages.storage.duckdb_store import DimensionColumn, DimensionDefinition

DIM_NODE = DimensionDefinition(
    table_name="dim_node",
    natural_key_columns=("hostname",),
    attribute_columns=(
        DimensionColumn("node_name", "VARCHAR"),
        DimensionColumn("role", "VARCHAR"),
        DimensionColumn("cpu", "VARCHAR"),
        DimensionColumn("ram_gb", "DECIMAL(10,2)"),
        DimensionColumn("os", "VARCHAR"),
    ),
)

DIM_DEVICE = DimensionDefinition(
    table_name="dim_device",
    natural_key_columns=("device_id",),
    attribute_columns=(
        DimensionColumn("device_name", "VARCHAR"),
        DimensionColumn("device_type", "VARCHAR"),
        DimensionColumn("location", "VARCHAR"),
        DimensionColumn("power_rating_watts", "DECIMAL(10,2)"),
    ),
)

CURRENT_DIM_NODE_VIEW = "rpt_current_dim_node"
CURRENT_DIM_DEVICE_VIEW = "rpt_current_dim_device"

FACT_CLUSTER_METRIC_TABLE = "fact_cluster_metric"

FACT_CLUSTER_METRIC_COLUMNS: list[tuple[str, str]] = [
    ("cluster_metric_id", "VARCHAR PRIMARY KEY"),
    ("run_id", "VARCHAR"),
    ("hostname", "VARCHAR NOT NULL"),
    ("node_name", "VARCHAR NOT NULL"),
    ("recorded_at", "TIMESTAMP NOT NULL"),
    ("metric_name", "VARCHAR NOT NULL"),
    ("metric_value", "DECIMAL(18,4) NOT NULL"),
    ("metric_unit", "VARCHAR"),
    ("source_system", "VARCHAR"),
]

FACT_POWER_CONSUMPTION_TABLE = "fact_power_consumption"

FACT_POWER_CONSUMPTION_COLUMNS: list[tuple[str, str]] = [
    ("power_consumption_id", "VARCHAR PRIMARY KEY"),
    ("run_id", "VARCHAR"),
    ("device_id", "VARCHAR NOT NULL"),
    ("device_name", "VARCHAR NOT NULL"),
    ("recorded_at", "TIMESTAMP NOT NULL"),
    ("watts", "DECIMAL(18,4) NOT NULL"),
    ("source_system", "VARCHAR"),
]


def cluster_metric_id(
    hostname: str,
    metric_name: str,
    recorded_at: str,
    metric_value: object,
) -> str:
    raw = f"{hostname}|{metric_name}|{recorded_at}|{metric_value}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def power_consumption_id(
    device_id: str,
    recorded_at: str,
    watts: object,
) -> str:
    raw = f"{device_id}|{recorded_at}|{watts}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
