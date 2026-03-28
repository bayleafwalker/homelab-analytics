"""Tests for the DuckDB versioned migration runner."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from packages.storage.migration_runner import apply_pending_duckdb_migrations

MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations" / "duckdb"

# Representative sample of tables that must exist after applying the baseline migration
_EXPECTED_TABLES = {
    # Immutable evidence layer
    "ingest_batch",
    "transaction_observation",
    # Entity + current projection
    "transaction_entity",
    "fact_transaction_current",
    "fact_balance_snapshot",
    # Core fact
    "fact_transaction",
    # Dimensions (SCD2)
    "dim_account",
    "dim_counterparty",
    "dim_category",
    "dim_loan",
    # Marts
    "mart_monthly_cashflow",
    "mart_account_balance_trend",
    # HA
    "dim_ha_entity",
    "fact_ha_state_change",
    # Scenario
    "dim_scenario",
    # Overview
    "mart_household_overview",
    # Category governance
    "category_rule",
    "category_override",
    # Migration tracking itself
    "schema_migrations",
}


@pytest.fixture()
def con() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(":memory:")


def _table_names(con: duckdb.DuckDBPyConnection) -> set[str]:
    return {row[0] for row in con.execute("SHOW TABLES").fetchall()}


def test_apply_baseline_migration(con: duckdb.DuckDBPyConnection) -> None:
    applied = apply_pending_duckdb_migrations(con, MIGRATIONS_DIR)
    assert applied == ["0001_initial_schema"]


def test_all_expected_tables_created(con: duckdb.DuckDBPyConnection) -> None:
    apply_pending_duckdb_migrations(con, MIGRATIONS_DIR)
    tables = _table_names(con)
    missing = _EXPECTED_TABLES - tables
    assert not missing, f"Missing tables after migration: {sorted(missing)}"


def test_schema_migrations_tracking_row(con: duckdb.DuckDBPyConnection) -> None:
    apply_pending_duckdb_migrations(con, MIGRATIONS_DIR)
    rows = con.execute("SELECT version FROM schema_migrations").fetchall()
    versions = {r[0] for r in rows}
    assert "0001_initial_schema" in versions


def test_idempotent_rerun(con: duckdb.DuckDBPyConnection) -> None:
    """Applying the same migrations twice must be a no-op on the second call."""
    applied1 = apply_pending_duckdb_migrations(con, MIGRATIONS_DIR)
    applied2 = apply_pending_duckdb_migrations(con, MIGRATIONS_DIR)
    assert applied1 == ["0001_initial_schema"]
    assert applied2 == []


def test_table_count_reasonable(con: duckdb.DuckDBPyConnection) -> None:
    """Sanity-check that we created the expected number of tables."""
    apply_pending_duckdb_migrations(con, MIGRATIONS_DIR)
    # schema_migrations + 66 warehouse tables (from generator script)
    count = con.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'main'").fetchone()[0]
    assert count >= 60, f"Expected at least 60 tables, got {count}"


def test_transaction_entity_default_status(con: duckdb.DuckDBPyConnection) -> None:
    """transaction_entity.status should default to 'active'."""
    apply_pending_duckdb_migrations(con, MIGRATIONS_DIR)
    con.execute(
        "INSERT INTO transaction_entity"
        " (entity_key, first_seen_batch_id, first_seen_at, last_seen_batch_id,"
        "  last_seen_at, current_observation_id)"
        " VALUES ('ek-1', 'b-1', CURRENT_TIMESTAMP, 'b-1', CURRENT_TIMESTAMP, 'obs-1')"
    )
    row = con.execute("SELECT status FROM transaction_entity WHERE entity_key = 'ek-1'").fetchone()
    assert row[0] == "active"
