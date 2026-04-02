"""Overlap test suite for overlapping bank statement ingestion scenarios.

Tests the three failure modes identified in the platform reassessment:

1. Exact duplicate batch (same file, same hash, same source_asset_id)
   → content-addressed batch_id means no new observations are written.

2. Same-hash reload (same content re-submitted under different run_id)
   → identical batch_id produced, ingest_batch insert is a no-op,
     observations already exist, reconciliation is idempotent.

3. Overlapping statements with different hashes (e.g. January full-month
   statement + January-February combined statement).
   → Different batch_ids, shared rows produce the same entity_key, so
     reconciliation deduplicates them at the entity layer — fact counts
     reflect unique entities, not raw row counts.

Also verifies that the old silent-double-count failure mode is gone:
loading the same transaction twice no longer inflates fact_transaction.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from packages.domains.finance.pipelines.transaction_models import (
    DIM_ACCOUNT,
    DIM_COUNTERPARTY,
    FACT_TRANSACTION_CURRENT_TABLE,
    FACT_TRANSACTION_TABLE,
    TRANSACTION_ENTITY_TABLE,
    TRANSACTION_OBSERVATION_TABLE,
)
from packages.domains.finance.pipelines.transformation_transactions import (
    INGEST_BATCH_TABLE,
)
from packages.domains.finance.pipelines.transformation_transactions import (
    load_transactions as _low_load,
)
from packages.pipelines.normalization import normalize_currency_code, normalize_timestamp_utc
from packages.pipelines.reconciliation import reconcile_batch
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

# January transactions (5 rows)
JANUARY_ROWS = [
    {
        "booked_at": date(2025, 1, 5),
        "account_id": "CHK-001",
        "counterparty_name": "Supermarket",
        "amount": "-42.80",
        "currency": "EUR",
        "description": "Weekly groceries",
    },
    {
        "booked_at": date(2025, 1, 10),
        "account_id": "CHK-001",
        "counterparty_name": "Electric Utility",
        "amount": "-84.15",
        "currency": "EUR",
        "description": "",
    },
    {
        "booked_at": date(2025, 1, 15),
        "account_id": "CHK-001",
        "counterparty_name": "Employer",
        "amount": "2450.00",
        "currency": "EUR",
        "description": "January salary",
    },
    {
        "booked_at": date(2025, 1, 20),
        "account_id": "CHK-001",
        "counterparty_name": "Landlord",
        "amount": "-950.00",
        "currency": "EUR",
        "description": "Rent",
    },
    {
        "booked_at": date(2025, 1, 28),
        "account_id": "CHK-001",
        "counterparty_name": "Gym",
        "amount": "-29.99",
        "currency": "EUR",
        "description": "",
    },
]

# February transactions (3 rows, no overlap with January)
FEBRUARY_ROWS = [
    {
        "booked_at": date(2025, 2, 3),
        "account_id": "CHK-001",
        "counterparty_name": "Supermarket",
        "amount": "-38.50",
        "currency": "EUR",
        "description": "Weekly groceries",
    },
    {
        "booked_at": date(2025, 2, 15),
        "account_id": "CHK-001",
        "counterparty_name": "Employer",
        "amount": "2450.00",
        "currency": "EUR",
        "description": "February salary",
    },
    {
        "booked_at": date(2025, 2, 20),
        "account_id": "CHK-001",
        "counterparty_name": "Landlord",
        "amount": "-950.00",
        "currency": "EUR",
        "description": "Rent Feb",
    },
]

# A "combined" statement covering Jan 20 – Feb 28: overlaps with the tail
# of January and all of February.
OVERLAP_ROWS = JANUARY_ROWS[3:] + FEBRUARY_ROWS  # Jan 20, Jan 28, Feb 3, Feb 15, Feb 20


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def svc() -> TransformationService:
    return TransformationService(DuckDBStore.memory())


def _normalize(row: dict) -> dict:
    amount = Decimal(str(row["amount"]))
    booked_at_utc = normalize_timestamp_utc(row["booked_at"])
    return {
        **row,
        "amount": amount,
        "booked_at_utc": booked_at_utc,
        "normalized_currency": normalize_currency_code(str(row.get("currency", ""))),
        "direction": "income" if amount >= 0 else "expense",
    }


def _load(
    svc: TransformationService,
    rows: list[dict],
    *,
    run_id: str,
    batch_sha256: str,
    source_asset_id: str = "asset-chk-001",
) -> str:
    """Write observations + facts without auto-reconciling. Returns batch_id."""
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


def _reconcile(svc: TransformationService, bid: str, run_id: str | None = None):
    return reconcile_batch(svc._store, bid, run_id=run_id)


def _obs_count(svc: TransformationService) -> int:
    return svc._store.fetchall(f"SELECT COUNT(*) FROM {TRANSACTION_OBSERVATION_TABLE}")[0][0]


def _entity_count(svc: TransformationService) -> int:
    return svc._store.fetchall(f"SELECT COUNT(*) FROM {TRANSACTION_ENTITY_TABLE}")[0][0]


def _fact_count(svc: TransformationService) -> int:
    return svc._store.fetchall(f"SELECT COUNT(*) FROM {FACT_TRANSACTION_TABLE}")[0][0]


def _current_count(svc: TransformationService) -> int:
    return svc._store.fetchall(f"SELECT COUNT(*) FROM {FACT_TRANSACTION_CURRENT_TABLE}")[0][0]


def _batch_count(svc: TransformationService) -> int:
    return svc._store.fetchall(f"SELECT COUNT(*) FROM {INGEST_BATCH_TABLE}")[0][0]


# ===========================================================================
# Failure mode 1: Exact duplicate batch (same sha256 + source_asset_id)
# ===========================================================================


def test_exact_duplicate_batch_produces_one_ingest_record(svc: TransformationService) -> None:
    """Re-loading the same file (same sha256) must not create a second batch record."""
    _load(svc, JANUARY_ROWS, run_id="run-001", batch_sha256="sha-jan")
    _load(svc, JANUARY_ROWS, run_id="run-001", batch_sha256="sha-jan")
    assert _batch_count(svc) == 1


def test_exact_duplicate_batch_produces_no_extra_observations(svc: TransformationService) -> None:
    """Re-loading the same file must not write duplicate observations."""
    _load(svc, JANUARY_ROWS, run_id="run-001", batch_sha256="sha-jan")
    obs_after_first = _obs_count(svc)
    _load(svc, JANUARY_ROWS, run_id="run-001", batch_sha256="sha-jan")
    assert _obs_count(svc) == obs_after_first


def test_exact_duplicate_reconcile_is_idempotent(svc: TransformationService) -> None:
    """Reconciling the same batch twice must not create extra entities."""
    bid = _load(svc, JANUARY_ROWS, run_id="run-001", batch_sha256="sha-jan")
    result1 = _reconcile(svc, bid, run_id="run-001")
    result2 = _reconcile(svc, bid)
    assert result1.new_entities == len(JANUARY_ROWS)
    assert result2.new_entities == 0
    assert result2.noop_updates == len(JANUARY_ROWS)
    assert _entity_count(svc) == len(JANUARY_ROWS)


# ===========================================================================
# Failure mode 2: Same content, different run_id (sha256 unchanged)
# ===========================================================================


def test_same_hash_different_run_id_is_noop(svc: TransformationService) -> None:
    """Same file content submitted under a new run_id produces no new batch or obs."""
    bid1 = _load(svc, JANUARY_ROWS, run_id="run-001", batch_sha256="sha-jan")
    _reconcile(svc, bid1, run_id="run-001")

    # Re-submit the same file under a new run_id (e.g. a re-triggered pipeline)
    bid2 = _load(svc, JANUARY_ROWS, run_id="run-002", batch_sha256="sha-jan")
    result2 = _reconcile(svc, bid2)

    # Same content-addressed batch_id → bid1 == bid2
    assert bid1 == bid2
    # Second reconcile: all existing entities, same obs_id already current → noops
    assert result2.new_entities == 0
    assert _batch_count(svc) == 1
    assert _obs_count(svc) == len(JANUARY_ROWS)


# ===========================================================================
# Failure mode 3: Overlapping statements with different hashes
# ===========================================================================


class TestOverlappingStatements:
    """Load January statement then an overlapping Jan-tail + Feb statement."""

    def test_no_double_count_in_fact_transaction(self, svc: TransformationService) -> None:
        """fact_transaction must contain unique transaction_ids — overlap rows skipped."""
        _load(svc, JANUARY_ROWS, run_id="run-001", batch_sha256="sha-jan")
        _load(svc, OVERLAP_ROWS, run_id="run-002", batch_sha256="sha-overlap")
        # fact_transaction uses ON CONFLICT DO NOTHING so the 2 overlapping rows
        # (Jan 20 Landlord + Jan 28 Gym) are not duplicated.
        unique_jan = len(JANUARY_ROWS)      # 5 rows from January batch
        new_feb = len(FEBRUARY_ROWS)        # 3 rows from February (non-overlapping)
        expected = unique_jan + new_feb     # = 8 unique transactions
        assert _fact_count(svc) == expected

    def test_observation_count_includes_all_evidence(self, svc: TransformationService) -> None:
        """All observations are stored (including overlapping ones as evidence)."""
        _load(svc, JANUARY_ROWS, run_id="run-001", batch_sha256="sha-jan")
        _load(svc, OVERLAP_ROWS, run_id="run-002", batch_sha256="sha-overlap")
        # 5 January + 5 overlap (2 shared + 3 new February) = 10 observations total
        assert _obs_count(svc) == len(JANUARY_ROWS) + len(OVERLAP_ROWS)

    def test_entity_count_reflects_unique_transactions(self, svc: TransformationService) -> None:
        """After reconciling both batches, entity count equals unique real-world transactions."""
        bid1 = _load(svc, JANUARY_ROWS, run_id="run-001", batch_sha256="sha-jan")
        _reconcile(svc, bid1, run_id="run-001")

        bid2 = _load(svc, OVERLAP_ROWS, run_id="run-002", batch_sha256="sha-overlap")
        result2 = _reconcile(svc, bid2, run_id="run-002")

        # 2 overlapping rows → noops; 3 new February rows → new entities
        assert result2.noop_updates == 2
        assert result2.new_entities == 3
        assert _entity_count(svc) == len(JANUARY_ROWS) + 3  # 5 Jan + 3 new Feb = 8

    def test_current_projection_shows_no_duplicates(self, svc: TransformationService) -> None:
        """fact_transaction_current must have the same count as unique entities."""
        bid1 = _load(svc, JANUARY_ROWS, run_id="run-001", batch_sha256="sha-jan")
        _reconcile(svc, bid1)
        bid2 = _load(svc, OVERLAP_ROWS, run_id="run-002", batch_sha256="sha-overlap")
        _reconcile(svc, bid2)

        assert _current_count(svc) == _entity_count(svc)

    def test_overlapping_enrichment_updates_current(self, svc: TransformationService) -> None:
        """If the second statement adds a description, current projection is updated."""
        # First load: Electric Utility row has no description
        bid1 = _load(svc, JANUARY_ROWS, run_id="run-001", batch_sha256="sha-jan")
        _reconcile(svc, bid1, run_id="run-001")

        # Second load: same Electric Utility row with description now filled in
        enriched_jan = [
            {**r, "description": "Monthly electricity"} if r["counterparty_name"] == "Electric Utility" else r
            for r in JANUARY_ROWS
        ]
        bid2 = _load(svc, enriched_jan, run_id="run-002", batch_sha256="sha-jan-enriched")
        result2 = _reconcile(svc, bid2, run_id="run-002")

        assert result2.richer_updates == 1

        desc = svc._store.fetchall(
            f"SELECT description FROM {FACT_TRANSACTION_CURRENT_TABLE}"
            f" WHERE counterparty_name = 'Electric Utility'"
        )[0][0]
        assert desc == "Monthly electricity"


# ===========================================================================
# Cross-account isolation
# ===========================================================================


def test_same_transaction_different_account_are_separate_entities(
    svc: TransformationService,
) -> None:
    """Two accounts with identical transaction fields produce separate entities."""
    row_a = {**JANUARY_ROWS[1], "account_id": "CHK-001"}
    row_b = {**JANUARY_ROWS[1], "account_id": "SAV-002"}

    bid = _load(
        svc, [row_a, row_b], run_id="run-001", batch_sha256="sha-cross-acct"
    )
    result = _reconcile(svc, bid)

    assert result.new_entities == 2
    assert _entity_count(svc) == 2


# ===========================================================================
# Observation count grows correctly across multiple overlapping loads
# ===========================================================================


def test_observation_count_increments_for_repeated_loads(svc: TransformationService) -> None:
    """Each time the same entity is seen in a new batch, observation_count increments."""
    # Batch A
    bid_a = _load(svc, JANUARY_ROWS[:1], run_id="run-001", batch_sha256="sha-a")
    _reconcile(svc, bid_a)

    # Batch B — same row, different hash (e.g. bank re-exported the statement)
    bid_b = _load(svc, JANUARY_ROWS[:1], run_id="run-002", batch_sha256="sha-b")
    _reconcile(svc, bid_b)

    # Batch C — another re-export
    bid_c = _load(svc, JANUARY_ROWS[:1], run_id="run-003", batch_sha256="sha-c")
    _reconcile(svc, bid_c)

    obs_count = svc._store.fetchall(
        f"SELECT observation_count FROM {TRANSACTION_ENTITY_TABLE}"
    )[0][0]
    assert obs_count == 3
    assert _entity_count(svc) == 1
