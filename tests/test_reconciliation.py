"""Tests for the transaction entity reconciliation engine."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from packages.pipelines.normalization import normalize_currency_code, normalize_timestamp_utc
from packages.pipelines.reconciliation import ReconciliationResult, reconcile_batch
from packages.pipelines.transaction_models import (
    DIM_ACCOUNT,
    DIM_COUNTERPARTY,
    FACT_TRANSACTION_CURRENT_TABLE,
    TRANSACTION_ENTITY_TABLE,
)
from packages.pipelines.transformation_service import TransformationService
from packages.pipelines.transformation_transactions import (
    TRANSACTION_OBSERVATION_TABLE,
    _batch_id,
)
from packages.pipelines.transformation_transactions import (
    load_transactions as _low_load,
)
from packages.storage.duckdb_store import DuckDBStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BASE_ROWS = [
    {
        "booked_at": date(2025, 1, 15),
        "account_id": "CHK-001",
        "counterparty_name": "Electric Utility",
        "amount": "-84.15",
        "currency": "EUR",
        "description": "",
    },
    {
        "booked_at": date(2025, 1, 20),
        "account_id": "CHK-001",
        "counterparty_name": "Employer",
        "amount": "2450.00",
        "currency": "EUR",
        "description": "January salary",
    },
]


@pytest.fixture()
def svc() -> TransformationService:
    return TransformationService(DuckDBStore.memory())


def _normalize(row: dict) -> dict:
    """Minimal normalizer for reconciliation tests."""
    amount = Decimal(str(row["amount"]))
    booked_at_utc = normalize_timestamp_utc(row["booked_at"])
    return {
        **row,
        "amount": amount,
        "booked_at_utc": booked_at_utc,
        "normalized_currency": normalize_currency_code(str(row.get("currency", ""))),
        "direction": "income" if amount >= 0 else "expense",
    }


def _load_only(
    svc: TransformationService,
    rows: list[dict],
    *,
    run_id: str,
    batch_sha256: str,
    source_asset_id: str,
) -> str:
    """Write observations to DB without reconciling. Returns batch_id."""
    _, bid = _low_load(
        svc._store,
        rows=rows,
        normalize_row=_normalize,
        record_lineage=lambda **kwargs: None,
        dim_account=DIM_ACCOUNT,
        dim_counterparty=DIM_COUNTERPARTY,
        run_id=run_id,
        batch_sha256=batch_sha256,
        source_asset_id=source_asset_id,
    )
    return bid


def _load_and_reconcile(
    svc: TransformationService,
    rows: list[dict],
    *,
    run_id: str = "run-001",
    batch_sha256: str = "sha-base",
    source_asset_id: str = "asset-1",
) -> ReconciliationResult:
    bid = _load_only(
        svc,
        rows,
        run_id=run_id,
        batch_sha256=batch_sha256,
        source_asset_id=source_asset_id,
    )
    return reconcile_batch(svc._store, bid, run_id=run_id)


# ---------------------------------------------------------------------------
# Outcome 1: New entity
# ---------------------------------------------------------------------------


def test_new_entities_created(svc: TransformationService) -> None:
    result = _load_and_reconcile(svc, BASE_ROWS)
    assert result.new_entities == 2
    assert result.total_observations == 2


def test_entity_table_has_correct_row_count(svc: TransformationService) -> None:
    _load_and_reconcile(svc, BASE_ROWS)
    count = svc._store.fetchall(f"SELECT COUNT(*) FROM {TRANSACTION_ENTITY_TABLE}")[0][0]
    assert count == 2


def test_current_projection_has_correct_row_count(svc: TransformationService) -> None:
    _load_and_reconcile(svc, BASE_ROWS)
    count = svc._store.fetchall(f"SELECT COUNT(*) FROM {FACT_TRANSACTION_CURRENT_TABLE}")[0][0]
    assert count == 2


def test_new_entity_status_is_active(svc: TransformationService) -> None:
    _load_and_reconcile(svc, BASE_ROWS)
    statuses = {
        r["status"]
        for r in svc._store.fetchall_dicts(f"SELECT status FROM {TRANSACTION_ENTITY_TABLE}")
    }
    assert statuses == {"active"}


def test_current_projection_has_correct_amounts(svc: TransformationService) -> None:
    _load_and_reconcile(svc, BASE_ROWS)
    rows = svc._store.fetchall_dicts(
        f"SELECT counterparty_name, amount FROM {FACT_TRANSACTION_CURRENT_TABLE}"
        f" ORDER BY counterparty_name"
    )
    assert rows[0]["counterparty_name"] == "Electric Utility"
    assert Decimal(str(rows[0]["amount"])) == Decimal("-84.15")


# ---------------------------------------------------------------------------
# Outcome 2: No-op (same canonical values)
# ---------------------------------------------------------------------------


def test_replay_same_batch_is_noop(svc: TransformationService) -> None:
    _load_and_reconcile(svc, BASE_ROWS, batch_sha256="sha-a")
    bid2 = _load_only(svc, BASE_ROWS, run_id="run-002", batch_sha256="sha-b", source_asset_id="asset-1")
    result2 = reconcile_batch(svc._store, bid2, run_id="run-002")

    assert result2.noop_updates == 2
    assert result2.new_entities == 0

    count = svc._store.fetchall(f"SELECT COUNT(*) FROM {TRANSACTION_ENTITY_TABLE}")[0][0]
    assert count == 2


def test_noop_increments_observation_count(svc: TransformationService) -> None:
    _load_and_reconcile(svc, BASE_ROWS[:1], batch_sha256="sha-a")
    bid2 = _load_only(
        svc, BASE_ROWS[:1], run_id="run-002", batch_sha256="sha-b", source_asset_id="asset-1"
    )
    reconcile_batch(svc._store, bid2)

    obs_count = svc._store.fetchall(
        f"SELECT observation_count FROM {TRANSACTION_ENTITY_TABLE}"
    )[0][0]
    assert obs_count == 2


# ---------------------------------------------------------------------------
# Outcome 3: Richer metadata
# ---------------------------------------------------------------------------


def test_richer_description_updates_current(svc: TransformationService) -> None:
    # First load: empty description
    _load_and_reconcile(svc, BASE_ROWS[:1], batch_sha256="sha-a")

    # Second load: same amount/currency but now has description
    enriched = [{**BASE_ROWS[0], "description": "Monthly electricity bill"}]
    bid2 = _load_only(
        svc, enriched, run_id="run-002", batch_sha256="sha-b", source_asset_id="asset-1"
    )
    result2 = reconcile_batch(svc._store, bid2, run_id="run-002")

    assert result2.richer_updates == 1

    updated = svc._store.fetchall_dicts(
        f"SELECT description FROM {FACT_TRANSACTION_CURRENT_TABLE}"
    )
    assert updated[0]["description"] == "Monthly electricity bill"


# ---------------------------------------------------------------------------
# Outcome 4: Conflict (differing amount on same entity_key)
#
# Conflict detection fires when two observations share the same entity_key
# (i.e., same identity tier resolved them to the same entity) but disagree
# on a canonical value.  With the bank tier-2 key (booked_at | account_id |
# amount | currency | counterparty_name), different amounts produce different
# keys — no conflict, just two entities.  A conflict requires a tier-1 key
# (provider_transaction_ref) so the same reference can be matched while the
# amount differs (e.g. a bank correction posting).
# ---------------------------------------------------------------------------


def _tier1_row(amount: str = "-84.15") -> dict:
    return {
        "booked_at": date(2025, 1, 15),
        "account_id": "CHK-001",
        "counterparty_name": "Electric Utility",
        "amount": amount,
        "currency": "EUR",
        "description": "",
        # tier-1 identity field — takes priority over composite key
        "provider_transaction_ref": "BKREF-20250115-001",
    }


def test_conflicting_amount_flags_entity_ambiguous(svc: TransformationService) -> None:
    """Same provider_transaction_ref + different amount = conflict."""
    _load_and_reconcile(svc, [_tier1_row("-84.15")], batch_sha256="sha-a")

    bid2 = _load_only(
        svc,
        [_tier1_row("-84.16")],  # same ref, 1 cent different
        run_id="run-002",
        batch_sha256="sha-b",
        source_asset_id="asset-1",
    )
    result2 = reconcile_batch(svc._store, bid2, run_id="run-002")

    assert result2.conflicts == 1

    entity = svc._store.fetchall_dicts(f"SELECT status FROM {TRANSACTION_ENTITY_TABLE}")[0]
    assert entity["status"] == "ambiguous"


def test_conflict_does_not_update_current_projection(svc: TransformationService) -> None:
    """Amount in current projection must be preserved when a conflicting observation arrives."""
    _load_and_reconcile(svc, [_tier1_row("-84.15")], batch_sha256="sha-a")
    original_amount = svc._store.fetchall(
        f"SELECT amount FROM {FACT_TRANSACTION_CURRENT_TABLE}"
    )[0][0]

    bid2 = _load_only(
        svc,
        [_tier1_row("-99.00")],
        run_id="run-002",
        batch_sha256="sha-b",
        source_asset_id="asset-1",
    )
    reconcile_batch(svc._store, bid2, run_id="run-002")

    after_amount = svc._store.fetchall(
        f"SELECT amount FROM {FACT_TRANSACTION_CURRENT_TABLE}"
    )[0][0]
    assert Decimal(str(after_amount)) == Decimal(str(original_amount)), (
        "Conflicting observation must not overwrite current projection"
    )


# ---------------------------------------------------------------------------
# Idempotent replay guard
# ---------------------------------------------------------------------------


def test_reconcile_same_batch_twice_is_idempotent(svc: TransformationService) -> None:
    result1 = _load_and_reconcile(svc, BASE_ROWS, batch_sha256="sha-a")
    bid = _batch_id("asset-1", "sha-a", "run-001")
    result2 = reconcile_batch(svc._store, bid)

    # Second run: all are noop (current_observation_id already matches)
    assert result2.new_entities == 0
    assert result2.noop_updates == result1.new_entities
    assert svc._store.fetchall(f"SELECT COUNT(*) FROM {TRANSACTION_ENTITY_TABLE}")[0][0] == 2


# ---------------------------------------------------------------------------
# Unresolved observations (entity_key IS NULL)
# ---------------------------------------------------------------------------


def test_unresolved_observations_are_skipped(svc: TransformationService) -> None:
    """Observations with no entity_key (identity resolution failed) are skipped."""
    bid = _batch_id("asset-1", "sha-null", "run-null")
    # Manually write a batch + observation with NULL entity_key
    svc._store.execute(
        "INSERT INTO ingest_batch (batch_id, run_id, source_asset_id, file_sha256,"
        " row_count, landed_at) VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)",
        [bid, "run-null", "asset-1", "sha-null"],
    )
    svc._store.execute(
        f"INSERT INTO {TRANSACTION_OBSERVATION_TABLE}"
        " (observation_id, batch_id, row_ordinal, entity_key, match_tier, confidence,"
        "  booked_at, account_id, counterparty_name, amount, currency, description,"
        "  normalized_row_json, observed_at)"
        " VALUES ('obs-null', ?, 0, NULL, NULL, NULL,"
        "  '2025-01-01', 'CHK-X', 'Unknown', 10.00, 'EUR', '',"
        "  '{}', CURRENT_TIMESTAMP)",
        [bid],
    )
    result = reconcile_batch(svc._store, bid)
    assert result.total_observations == 0
    assert result.new_entities == 0


# ---------------------------------------------------------------------------
# ReconciliationResult fields
# ---------------------------------------------------------------------------


def test_reconciliation_result_fields(svc: TransformationService) -> None:
    result = _load_and_reconcile(svc, BASE_ROWS)
    assert result.batch_id is not None
    assert result.new_entities == 2
    assert result.noop_updates == 0
    assert result.richer_updates == 0
    assert result.conflicts == 0
    assert result.total_observations == 2
