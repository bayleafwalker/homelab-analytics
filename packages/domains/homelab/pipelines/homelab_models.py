"""Homelab domain table and mart definitions.

Defines canonical storage for service health, backup runs, storage sensors,
and workload sensors, plus the four mart tables derived from them.
"""
from __future__ import annotations

import hashlib

from packages.storage.duckdb_store import DimensionColumn, DimensionDefinition

# ---------------------------------------------------------------------------
# Dimensions
# ---------------------------------------------------------------------------

DIM_SERVICE = DimensionDefinition(
    table_name="dim_service",
    natural_key_columns=("service_id",),
    attribute_columns=(
        DimensionColumn("service_name", "VARCHAR"),
        DimensionColumn("service_type", "VARCHAR"),   # container | vm | addon | integration
        DimensionColumn("host", "VARCHAR"),
        DimensionColumn("criticality", "VARCHAR"),    # critical | standard | background
        DimensionColumn("managed_by", "VARCHAR"),     # homeassistant | portainer | manual
    ),
)

DIM_WORKLOAD = DimensionDefinition(
    table_name="dim_workload",
    natural_key_columns=("workload_id",),
    attribute_columns=(
        DimensionColumn("entity_id", "VARCHAR"),
        DimensionColumn("display_name", "VARCHAR"),
        DimensionColumn("host", "VARCHAR"),
        DimensionColumn("workload_type", "VARCHAR"),  # container | vm | process
    ),
)

CURRENT_DIM_SERVICE_VIEW = "rpt_current_dim_service"
CURRENT_DIM_WORKLOAD_VIEW = "rpt_current_dim_workload"

# ---------------------------------------------------------------------------
# Fact: service health
# ---------------------------------------------------------------------------

FACT_SERVICE_HEALTH_TABLE = "fact_service_health"

FACT_SERVICE_HEALTH_COLUMNS: list[tuple[str, str]] = [
    ("health_id", "VARCHAR PRIMARY KEY"),
    ("run_id", "VARCHAR"),
    ("service_id", "VARCHAR NOT NULL"),
    ("recorded_at", "TIMESTAMP NOT NULL"),
    ("state", "VARCHAR NOT NULL"),        # running | stopped | degraded | unknown
    ("uptime_seconds", "BIGINT"),
    ("last_state_change", "TIMESTAMP"),
]

# ---------------------------------------------------------------------------
# Fact: backup runs
# ---------------------------------------------------------------------------

FACT_BACKUP_RUN_TABLE = "fact_backup_run"

FACT_BACKUP_RUN_COLUMNS: list[tuple[str, str]] = [
    ("backup_id", "VARCHAR PRIMARY KEY"),
    ("run_id", "VARCHAR"),
    ("started_at", "TIMESTAMP NOT NULL"),
    ("completed_at", "TIMESTAMP"),
    ("duration_s", "INTEGER"),
    ("size_bytes", "BIGINT"),
    ("target", "VARCHAR NOT NULL"),       # nas | s3 | local
    ("status", "VARCHAR NOT NULL"),       # success | partial | failed
]

# ---------------------------------------------------------------------------
# Fact: storage sensors
# ---------------------------------------------------------------------------

FACT_STORAGE_SENSOR_TABLE = "fact_storage_sensor"

FACT_STORAGE_SENSOR_COLUMNS: list[tuple[str, str]] = [
    ("sensor_id", "VARCHAR PRIMARY KEY"),
    ("run_id", "VARCHAR"),
    ("entity_id", "VARCHAR NOT NULL"),
    ("device_name", "VARCHAR NOT NULL"),
    ("recorded_at", "TIMESTAMP NOT NULL"),
    ("capacity_bytes", "BIGINT NOT NULL"),
    ("used_bytes", "BIGINT NOT NULL"),
    ("sensor_type", "VARCHAR"),
]

# ---------------------------------------------------------------------------
# Fact: workload sensors
# ---------------------------------------------------------------------------

FACT_WORKLOAD_SENSOR_TABLE = "fact_workload_sensor"

FACT_WORKLOAD_SENSOR_COLUMNS: list[tuple[str, str]] = [
    ("reading_id", "VARCHAR PRIMARY KEY"),
    ("run_id", "VARCHAR"),
    ("workload_id", "VARCHAR NOT NULL"),
    ("entity_id", "VARCHAR NOT NULL"),
    ("recorded_at", "TIMESTAMP NOT NULL"),
    ("cpu_pct", "DECIMAL(6,3)"),
    ("mem_bytes", "BIGINT"),
]

# ---------------------------------------------------------------------------
# Mart: service_health_current
# ---------------------------------------------------------------------------

MART_SERVICE_HEALTH_CURRENT_TABLE = "mart_service_health_current"

MART_SERVICE_HEALTH_CURRENT_COLUMNS: list[tuple[str, str]] = [
    ("service_id", "VARCHAR NOT NULL"),
    ("service_name", "VARCHAR"),
    ("service_type", "VARCHAR"),
    ("host", "VARCHAR"),
    ("criticality", "VARCHAR"),
    ("managed_by", "VARCHAR"),
    ("state", "VARCHAR NOT NULL"),
    ("uptime_seconds", "BIGINT"),
    ("last_state_change", "TIMESTAMP"),
    ("recorded_at", "TIMESTAMP NOT NULL"),
]

# ---------------------------------------------------------------------------
# Mart: backup_freshness
# ---------------------------------------------------------------------------

MART_BACKUP_FRESHNESS_TABLE = "mart_backup_freshness"

MART_BACKUP_FRESHNESS_COLUMNS: list[tuple[str, str]] = [
    ("target", "VARCHAR NOT NULL"),
    ("last_backup_at", "TIMESTAMP"),
    ("last_status", "VARCHAR"),
    ("last_size_bytes", "BIGINT"),
    ("hours_since_backup", "DECIMAL(10,2)"),
    ("is_stale", "BOOLEAN NOT NULL"),     # TRUE when >24h since last success
    ("backup_count_7d", "INTEGER"),
]

# ---------------------------------------------------------------------------
# Mart: storage_risk
# ---------------------------------------------------------------------------

MART_STORAGE_RISK_TABLE = "mart_storage_risk"

MART_STORAGE_RISK_COLUMNS: list[tuple[str, str]] = [
    ("entity_id", "VARCHAR NOT NULL"),
    ("device_name", "VARCHAR NOT NULL"),
    ("recorded_at", "TIMESTAMP NOT NULL"),
    ("capacity_bytes", "BIGINT NOT NULL"),
    ("used_bytes", "BIGINT NOT NULL"),
    ("free_bytes", "BIGINT NOT NULL"),
    ("pct_used", "DECIMAL(6,3) NOT NULL"),
    ("risk_tier", "VARCHAR NOT NULL"),    # ok | warn | crit
]

# ---------------------------------------------------------------------------
# Mart: workload_cost_7d
# ---------------------------------------------------------------------------

MART_WORKLOAD_COST_7D_TABLE = "mart_workload_cost_7d"

MART_WORKLOAD_COST_7D_COLUMNS: list[tuple[str, str]] = [
    ("workload_id", "VARCHAR NOT NULL"),
    ("display_name", "VARCHAR"),
    ("host", "VARCHAR"),
    ("workload_type", "VARCHAR"),
    ("avg_cpu_pct_7d", "DECIMAL(6,3)"),
    ("avg_mem_gb_7d", "DECIMAL(10,4)"),
    ("reading_count_7d", "INTEGER"),
    ("est_monthly_cost", "DECIMAL(10,4)"),  # simple heuristic: cpu+mem cost model
]

# ---------------------------------------------------------------------------
# ID helpers
# ---------------------------------------------------------------------------

def service_health_id(service_id: str, recorded_at: str) -> str:
    return hashlib.sha1(f"{service_id}|{recorded_at}".encode()).hexdigest()[:16]


def storage_sensor_id(entity_id: str, recorded_at: str) -> str:
    return hashlib.sha1(f"{entity_id}|{recorded_at}".encode()).hexdigest()[:16]


def workload_reading_id(workload_id: str, recorded_at: str) -> str:
    return hashlib.sha1(f"{workload_id}|{recorded_at}".encode()).hexdigest()[:16]
