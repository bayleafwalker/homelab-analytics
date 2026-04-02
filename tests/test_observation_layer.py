"""Tests for the immutable ingest_batch + transaction_observation dual-write layer."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from packages.domains.finance.pipelines.transformation_transactions import (
    INGEST_BATCH_TABLE,
    TRANSACTION_OBSERVATION_TABLE,
    _batch_id,
    _normalized_observation_json,
    _observation_id,
)
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

LANDING_ROWS = [
    {
        "booked_at": date(2025, 1, 15),
        "account_id": "CHK-001",
        "counterparty_name": "Electric Utility",
        "amount": "-84.15",
        "currency": "EUR",
        "description": "Monthly bill",
    },
    {
        "booked_at": date(2025, 1, 20),
        "account_id": "CHK-001",
        "counterparty_name": "Employer",
        "amount": "2450.00",
        "currency": "EUR",
        "description": "Salary",
    },
    {
        "booked_at": date(2025, 1, 25),
        "account_id": "SAV-001",
        "counterparty_name": "Transfer In",
        "amount": "500.00",
        "currency": "EUR",
        "description": "",
    },
]


@pytest.fixture()
def svc() -> TransformationService:
    return TransformationService(DuckDBStore.memory())


# ---------------------------------------------------------------------------
# _batch_id helper
# ---------------------------------------------------------------------------


def test_batch_id_content_addressed_when_sha_provided() -> None:
    bid1 = _batch_id("asset-1", "abc123", "run-999")
    bid2 = _batch_id("asset-1", "abc123", "run-different")
    assert bid1 == bid2, "Same source+SHA should produce same batch_id regardless of run_id"


def test_batch_id_differs_for_different_sha() -> None:
    bid1 = _batch_id("asset-1", "abc123", "run-001")
    bid2 = _batch_id("asset-1", "def456", "run-001")
    assert bid1 != bid2


def test_batch_id_falls_back_to_run_id() -> None:
    bid = _batch_id(None, None, "run-abc")
    assert bid == "run-abc"[:16]


def test_batch_id_generates_uuid_when_all_none() -> None:
    bid = _batch_id(None, None, None)
    assert len(bid) == 16


# ---------------------------------------------------------------------------
# _normalized_observation_json helper
# ---------------------------------------------------------------------------


def test_normalized_observation_json_is_deterministic() -> None:
    row = {"booked_at": date(2025, 1, 1), "account_id": "A", "counterparty_name": "B",
           "amount": Decimal("10.00"), "currency": "EUR", "description": "x"}
    j1 = _normalized_observation_json(row)
    j2 = _normalized_observation_json(row)
    assert j1 == j2


def test_normalized_observation_json_description_none_becomes_empty() -> None:
    row = {"booked_at": date(2025, 1, 1), "account_id": "A", "counterparty_name": "B",
           "amount": Decimal("10.00"), "currency": "EUR", "description": None}
    j = _normalized_observation_json(row)
    assert '"description": ""' in j


# ---------------------------------------------------------------------------
# _observation_id helper
# ---------------------------------------------------------------------------


def test_observation_id_is_deterministic() -> None:
    oid1 = _observation_id("batch-1", 0, '{"amount": "10"}')
    oid2 = _observation_id("batch-1", 0, '{"amount": "10"}')
    assert oid1 == oid2


def test_observation_id_differs_by_ordinal() -> None:
    oid0 = _observation_id("batch-1", 0, '{"amount": "10"}')
    oid1 = _observation_id("batch-1", 1, '{"amount": "10"}')
    assert oid0 != oid1


def test_observation_id_differs_by_batch() -> None:
    oid_a = _observation_id("batch-a", 0, '{"amount": "10"}')
    oid_b = _observation_id("batch-b", 0, '{"amount": "10"}')
    assert oid_a != oid_b


# ---------------------------------------------------------------------------
# Dual-write: ingest_batch populated on load_transactions
# ---------------------------------------------------------------------------


def test_load_transactions_writes_batch_row(svc: TransformationService) -> None:
    svc.load_transactions(LANDING_ROWS, run_id="run-001", batch_sha256="sha-abc", source_asset_id="asset-1")
    batches = svc._store.fetchall_dicts(f"SELECT * FROM {INGEST_BATCH_TABLE}")
    assert len(batches) == 1
    assert batches[0]["run_id"] == "run-001"
    assert batches[0]["file_sha256"] == "sha-abc"
    assert batches[0]["source_asset_id"] == "asset-1"
    assert batches[0]["row_count"] == 3


def test_load_transactions_batch_row_count_matches_rows(svc: TransformationService) -> None:
    svc.load_transactions(LANDING_ROWS[:2], run_id="run-001")
    batches = svc._store.fetchall_dicts(f"SELECT * FROM {INGEST_BATCH_TABLE}")
    assert batches[0]["row_count"] == 2


def test_batch_id_is_content_addressed_when_sha_provided(svc: TransformationService) -> None:
    svc.load_transactions(LANDING_ROWS, run_id="run-001", batch_sha256="same-sha", source_asset_id="asset-1")
    svc.load_transactions(LANDING_ROWS, run_id="run-002", batch_sha256="same-sha", source_asset_id="asset-1")
    batches = svc._store.fetchall_dicts(f"SELECT * FROM {INGEST_BATCH_TABLE}")
    assert len(batches) == 1, "Same content should produce same batch_id — second insert should be ignored"


def test_different_sha_produces_new_batch(svc: TransformationService) -> None:
    svc.load_transactions(LANDING_ROWS, run_id="run-001", batch_sha256="sha-a", source_asset_id="asset-1")
    svc.load_transactions(LANDING_ROWS, run_id="run-002", batch_sha256="sha-b", source_asset_id="asset-1")
    batches = svc._store.fetchall_dicts(f"SELECT * FROM {INGEST_BATCH_TABLE}")
    assert len(batches) == 2


# ---------------------------------------------------------------------------
# Dual-write: transaction_observation populated on load_transactions
# ---------------------------------------------------------------------------


def test_load_transactions_writes_observation_rows(svc: TransformationService) -> None:
    svc.load_transactions(LANDING_ROWS, run_id="run-001")
    obs = svc._store.fetchall_dicts(f"SELECT * FROM {TRANSACTION_OBSERVATION_TABLE}")
    assert len(obs) == len(LANDING_ROWS)


def test_observations_have_entity_key(svc: TransformationService) -> None:
    svc.load_transactions(LANDING_ROWS, run_id="run-001")
    obs = svc._store.fetchall_dicts(f"SELECT entity_key, match_tier FROM {TRANSACTION_OBSERVATION_TABLE}")
    for row in obs:
        assert row["entity_key"] is not None, "All rows have sufficient fields for tier-2 match"
        assert row["match_tier"] == 2


def test_observations_have_correct_ordinals(svc: TransformationService) -> None:
    svc.load_transactions(LANDING_ROWS, run_id="run-001")
    obs = svc._store.fetchall_dicts(
        f"SELECT row_ordinal FROM {TRANSACTION_OBSERVATION_TABLE} ORDER BY row_ordinal"
    )
    assert [r["row_ordinal"] for r in obs] == [0, 1, 2]


def test_observations_link_to_batch(svc: TransformationService) -> None:
    svc.load_transactions(LANDING_ROWS, run_id="run-001")
    batch_ids = {r["batch_id"] for r in svc._store.fetchall_dicts(
        f"SELECT batch_id FROM {TRANSACTION_OBSERVATION_TABLE}"
    )}
    batch_row_ids = {r["batch_id"] for r in svc._store.fetchall_dicts(
        f"SELECT batch_id FROM {INGEST_BATCH_TABLE}"
    )}
    assert batch_ids == batch_row_ids


def test_observations_are_idempotent_with_same_content(svc: TransformationService) -> None:
    """Replaying the same batch (same sha256) produces no new observation rows."""
    svc.load_transactions(LANDING_ROWS, run_id="run-001", batch_sha256="sha-abc", source_asset_id="asset-1")
    svc.load_transactions(LANDING_ROWS, run_id="run-001", batch_sha256="sha-abc", source_asset_id="asset-1")
    obs = svc._store.fetchall_dicts(f"SELECT * FROM {TRANSACTION_OBSERVATION_TABLE}")
    assert len(obs) == len(LANDING_ROWS)


def test_observation_ids_are_unique_across_rows(svc: TransformationService) -> None:
    svc.load_transactions(LANDING_ROWS, run_id="run-001")
    ids = [r["observation_id"] for r in svc._store.fetchall_dicts(
        f"SELECT observation_id FROM {TRANSACTION_OBSERVATION_TABLE}"
    )]
    assert len(ids) == len(set(ids)), "observation_ids must be unique"


def test_observations_preserve_canonical_fields(svc: TransformationService) -> None:
    svc.load_transactions(LANDING_ROWS, run_id="run-001")
    obs = svc._store.fetchall_dicts(
        f"SELECT account_id, counterparty_name, currency FROM {TRANSACTION_OBSERVATION_TABLE}"
        f" ORDER BY row_ordinal"
    )
    assert obs[0]["account_id"] == "CHK-001"
    assert obs[0]["counterparty_name"] == "Electric Utility"
    assert obs[0]["currency"] == "EUR"


# ---------------------------------------------------------------------------
# Backward compat: fact_transaction still populated
# ---------------------------------------------------------------------------


def test_fact_transaction_still_populated(svc: TransformationService) -> None:
    inserted = svc.load_transactions(LANDING_ROWS, run_id="run-001")
    assert inserted == len(LANDING_ROWS)
    rows = svc._store.fetchall("SELECT COUNT(*) FROM fact_transaction")
    assert rows[0][0] == len(LANDING_ROWS)


def test_fact_and_observations_row_counts_match(svc: TransformationService) -> None:
    svc.load_transactions(LANDING_ROWS, run_id="run-001")
    fact_count = svc._store.fetchall("SELECT COUNT(*) FROM fact_transaction")[0][0]
    obs_count = svc._store.fetchall(f"SELECT COUNT(*) FROM {TRANSACTION_OBSERVATION_TABLE}")[0][0]
    assert fact_count == obs_count
