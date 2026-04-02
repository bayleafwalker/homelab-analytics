"""Tests for dim_account, dim_counterparty definitions and extraction helpers."""

from __future__ import annotations

from datetime import date

import pytest

from packages.domains.finance.pipelines.transaction_models import (
    DIM_ACCOUNT,
    DIM_COUNTERPARTY,
    extract_accounts,
    extract_counterparties,
)
from packages.storage.duckdb_store import DuckDBStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_ROWS = [
    {
        "account_id": "CHK-001",
        "counterparty_name": "Electric Utility",
        "amount": -84.15,
        "currency": "EUR",
        "description": "Monthly bill",
    },
    {
        "account_id": "CHK-001",
        "counterparty_name": "Employer",
        "amount": 2450.00,
        "currency": "EUR",
        "description": "Salary",
    },
    {
        "account_id": "SAV-001",
        "counterparty_name": "Electric Utility",
        "amount": -50.00,
        "currency": "EUR",
        "description": "Transfer",
    },
]


@pytest.fixture()
def store() -> DuckDBStore:
    s = DuckDBStore.memory()
    s.ensure_dimension(DIM_ACCOUNT)
    s.ensure_dimension(DIM_COUNTERPARTY)
    return s


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------


def test_extract_accounts_deduplicated() -> None:
    accounts = extract_accounts(SAMPLE_ROWS)
    ids = [a["account_id"] for a in accounts]
    assert sorted(ids) == ["CHK-001", "SAV-001"]


def test_extract_counterparties_deduplicated() -> None:
    counterparties = extract_counterparties(SAMPLE_ROWS)
    names = [c["counterparty_name"] for c in counterparties]
    assert sorted(names) == ["Electric Utility", "Employer"]


def test_extract_counterparties_category_is_none() -> None:
    counterparties = extract_counterparties(SAMPLE_ROWS)
    assert all(c["category"] is None for c in counterparties)


# ---------------------------------------------------------------------------
# Dimension upsert round-trip
# ---------------------------------------------------------------------------


def test_dim_account_upsert(store: DuckDBStore) -> None:
    accounts = extract_accounts(SAMPLE_ROWS)
    inserted = store.upsert_dimension_rows(DIM_ACCOUNT, accounts, effective_date=date(2025, 1, 1))
    assert inserted == 2
    current = store.query_current(DIM_ACCOUNT)
    assert len(current) == 2
    ids = {r["account_id"] for r in current}
    assert ids == {"CHK-001", "SAV-001"}


def test_dim_counterparty_upsert(store: DuckDBStore) -> None:
    counterparties = extract_counterparties(SAMPLE_ROWS)
    inserted = store.upsert_dimension_rows(
        DIM_COUNTERPARTY, counterparties, effective_date=date(2025, 1, 1)
    )
    assert inserted == 2
    current = store.query_current(DIM_COUNTERPARTY)
    names = {r["counterparty_name"] for r in current}
    assert names == {"Electric Utility", "Employer"}


def test_dim_counterparty_category_update_creates_version(store: DuckDBStore) -> None:
    """When a counterparty gets categorised, a new SCD version is created."""
    store.upsert_dimension_rows(
        DIM_COUNTERPARTY,
        [{"counterparty_name": "Electric Utility", "category": None, "category_id": None}],
        effective_date=date(2025, 1, 1),
    )
    store.upsert_dimension_rows(
        DIM_COUNTERPARTY,
        [{"counterparty_name": "Electric Utility", "category": "Utilities", "category_id": None}],
        effective_date=date(2025, 3, 1),
    )
    current = store.query_current(DIM_COUNTERPARTY)
    assert len(current) == 1
    assert current[0]["category"] == "Utilities"

    history = store.query_as_of(DIM_COUNTERPARTY, date(2025, 2, 1))
    assert history[0]["category"] is None
