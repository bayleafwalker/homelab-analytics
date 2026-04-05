"""Tests for the DuckDB-backed SCD Type 2 dimension engine."""

from __future__ import annotations

from datetime import date

import pytest

from packages.storage.duckdb_store import (
    DimensionColumn,
    DimensionDefinition,
    DuckDBStore,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_DIM_ACCOUNT = DimensionDefinition(
    table_name="dim_account",
    natural_key_columns=("account_id",),
    attribute_columns=(
        DimensionColumn("account_name", "VARCHAR"),
        DimensionColumn("institution", "VARCHAR"),
    ),
)


@pytest.fixture()
def store() -> DuckDBStore:
    s = DuckDBStore.memory()
    s.ensure_dimension(_DIM_ACCOUNT)
    return s


# ---------------------------------------------------------------------------
# Insert new rows
# ---------------------------------------------------------------------------


def test_insert_new_row(store: DuckDBStore) -> None:
    inserted = store.upsert_dimension_rows(
        _DIM_ACCOUNT,
        [{"account_id": "CHK-001", "account_name": "Checking", "institution": "Bank A"}],
        effective_date=date(2025, 1, 1),
    )
    assert inserted == 1
    rows = store.query_current(_DIM_ACCOUNT)
    assert len(rows) == 1
    assert rows[0]["account_id"] == "CHK-001"
    assert rows[0]["account_name"] == "Checking"
    assert rows[0]["institution"] == "Bank A"


def test_insert_multiple_new_rows(store: DuckDBStore) -> None:
    rows_in = [
        {"account_id": "CHK-001", "account_name": "Checking", "institution": "Bank A"},
        {"account_id": "SAV-001", "account_name": "Savings", "institution": "Bank A"},
    ]
    inserted = store.upsert_dimension_rows(_DIM_ACCOUNT, rows_in, effective_date=date(2025, 1, 1))
    assert inserted == 2
    assert len(store.query_current(_DIM_ACCOUNT)) == 2


# ---------------------------------------------------------------------------
# No-change upsert (same attributes) → no new version
# ---------------------------------------------------------------------------


def test_upsert_no_change(store: DuckDBStore) -> None:
    row = {"account_id": "CHK-001", "account_name": "Checking", "institution": "Bank A"}
    store.upsert_dimension_rows(_DIM_ACCOUNT, [row], effective_date=date(2025, 1, 1))
    inserted = store.upsert_dimension_rows(_DIM_ACCOUNT, [row], effective_date=date(2025, 6, 1))
    assert inserted == 0
    # Still only one row total
    total = store.fetchall(f"SELECT COUNT(*) FROM {_DIM_ACCOUNT.table_name}")
    assert total[0][0] == 1


# ---------------------------------------------------------------------------
# Attribute change → SCD Type 2 versioning
# ---------------------------------------------------------------------------


def test_attribute_change_creates_new_version(store: DuckDBStore) -> None:
    row_v1 = {"account_id": "CHK-001", "account_name": "Checking", "institution": "Bank A"}
    store.upsert_dimension_rows(_DIM_ACCOUNT, [row_v1], effective_date=date(2025, 1, 1))

    row_v2 = {"account_id": "CHK-001", "account_name": "Checking Plus", "institution": "Bank A"}
    inserted = store.upsert_dimension_rows(_DIM_ACCOUNT, [row_v2], effective_date=date(2025, 6, 1))
    assert inserted == 1

    # Two rows total
    total = store.fetchall(f"SELECT COUNT(*) FROM {_DIM_ACCOUNT.table_name}")
    assert total[0][0] == 2

    # Current view shows v2 only
    current = store.query_current(_DIM_ACCOUNT)
    assert len(current) == 1
    assert current[0]["account_name"] == "Checking Plus"

    # Old version is closed
    old = store.fetchall_dicts(
        f"SELECT * FROM {_DIM_ACCOUNT.table_name} WHERE is_current = FALSE"
    )
    assert len(old) == 1
    assert old[0]["account_name"] == "Checking"
    assert old[0]["valid_to"] == date(2025, 6, 1)


# ---------------------------------------------------------------------------
# Point-in-time queries
# ---------------------------------------------------------------------------


def test_point_in_time_query(store: DuckDBStore) -> None:
    row_v1 = {"account_id": "CHK-001", "account_name": "Checking", "institution": "Bank A"}
    store.upsert_dimension_rows(_DIM_ACCOUNT, [row_v1], effective_date=date(2025, 1, 1))

    row_v2 = {"account_id": "CHK-001", "account_name": "Checking Plus", "institution": "Bank A"}
    store.upsert_dimension_rows(_DIM_ACCOUNT, [row_v2], effective_date=date(2025, 6, 1))

    # Query before change → sees v1
    before = store.query_as_of(_DIM_ACCOUNT, date(2025, 3, 15))
    assert len(before) == 1
    assert before[0]["account_name"] == "Checking"

    # Query after change → sees v2
    after = store.query_as_of(_DIM_ACCOUNT, date(2025, 7, 1))
    assert len(after) == 1
    assert after[0]["account_name"] == "Checking Plus"


def test_point_in_time_before_any_version(store: DuckDBStore) -> None:
    store.upsert_dimension_rows(
        _DIM_ACCOUNT,
        [{"account_id": "CHK-001", "account_name": "Checking", "institution": "Bank A"}],
        effective_date=date(2025, 6, 1),
    )
    result = store.query_as_of(_DIM_ACCOUNT, date(2024, 12, 31))
    assert result == []


# ---------------------------------------------------------------------------
# Empty input
# ---------------------------------------------------------------------------


def test_upsert_empty_list(store: DuckDBStore) -> None:
    assert store.upsert_dimension_rows(_DIM_ACCOUNT, []) == 0


# ---------------------------------------------------------------------------
# ensure_dimension is idempotent
# ---------------------------------------------------------------------------


def test_ensure_dimension_idempotent(store: DuckDBStore) -> None:
    store.ensure_dimension(_DIM_ACCOUNT)  # already created in fixture
    # Should not raise
    store.ensure_dimension(_DIM_ACCOUNT)


# ---------------------------------------------------------------------------
# Surrogate key uniqueness
# ---------------------------------------------------------------------------


def test_surrogate_keys_are_unique(store: DuckDBStore) -> None:
    store.upsert_dimension_rows(
        _DIM_ACCOUNT,
        [
            {"account_id": "CHK-001", "account_name": "Checking", "institution": "Bank A"},
            {"account_id": "SAV-001", "account_name": "Savings", "institution": "Bank B"},
        ],
        effective_date=date(2025, 1, 1),
    )
    sks = store.fetchall(f"SELECT sk FROM {_DIM_ACCOUNT.table_name}")
    assert len(set(row[0] for row in sks)) == 2
