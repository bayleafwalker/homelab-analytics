"""Tests for confidence enrichment in publication contract export.

This test suite verifies that the export_contracts function and
build_publication_contract_catalog correctly enrich publication contracts
with confidence metadata when a control plane store with snapshots is provided.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from packages.domains.finance.manifest import FINANCE_PACK
from packages.domains.homelab.manifest import HOMELAB_PACK
from packages.domains.overview.manifest import OVERVIEW_PACK
from packages.domains.utilities.manifest import UTILITIES_PACK
from packages.pipelines.composition.current_dimension_contracts import (
    CURRENT_DIMENSION_CONTRACTS,
)
from packages.pipelines.household_reporting import (
    CURRENT_DIMENSION_RELATIONS,
    PUBLICATION_RELATIONS,
)
from packages.platform.publication_contracts import build_publication_contract_catalog
from packages.storage.control_plane import PublicationConfidenceSnapshotCreate
from packages.storage.ingestion_config import IngestionConfigRepository

pytestmark = [pytest.mark.architecture]


def test_export_contracts_enriches_with_confidence_fields_when_snapshot_exists() -> None:
    """Verify that confidence fields are populated when a snapshot exists in control plane.

    This test:
    1. Creates an in-memory control plane store (SQLite)
    2. Records a publication confidence snapshot with known values
    3. Builds a publication contract catalog with the store
    4. Asserts that the resulting contracts have non-null confidence fields
    """
    with TemporaryDirectory() as temp_dir:
        # 1. Build a control plane store (SQLite)
        control_plane_store = IngestionConfigRepository(Path(temp_dir) / "config.db")

        # 2. Record a confidence snapshot
        now = datetime(2026, 4, 15, 12, 0, 0, tzinfo=UTC)
        snapshot = PublicationConfidenceSnapshotCreate(
            snapshot_id="test-snapshot-001",
            publication_key="monthly_cashflow",
            assessed_at=now,
            freshness_state="current",
            completeness_pct=100,
            confidence_verdict="trustworthy",
            quality_flags=None,
            contributing_run_ids=("run-001", "run-002"),
        )
        control_plane_store.record_publication_confidence_snapshot((snapshot,))

        # 3. Build publication contract catalog with control plane
        catalog = build_publication_contract_catalog(
            (FINANCE_PACK, UTILITIES_PACK, OVERVIEW_PACK, HOMELAB_PACK),
            publication_relations=PUBLICATION_RELATIONS,
            current_dimension_relations=CURRENT_DIMENSION_RELATIONS,
            current_dimension_contracts=CURRENT_DIMENSION_CONTRACTS,
            control_plane=control_plane_store,
        )

        # 4. Extract the monthly_cashflow contract
        publication_contracts = catalog["publication_contracts"]
        assert isinstance(publication_contracts, list)

        monthly_cashflow = next(
            (c for c in publication_contracts if c.publication_key == "monthly_cashflow"),
            None,
        )
        assert monthly_cashflow is not None, "monthly_cashflow publication not found in catalog"

        # 5. Assert confidence fields are non-null and match the snapshot
        assert monthly_cashflow.confidence_verdict == "trustworthy"
        assert monthly_cashflow.freshness_state == "current"
        assert monthly_cashflow.completeness_pct == 100
        assert monthly_cashflow.assessed_at == now.isoformat()


def test_export_contracts_has_none_confidence_fields_without_snapshot() -> None:
    """Verify that confidence fields remain None when no snapshot exists.

    This test confirms that contracts without a matching snapshot
    have null confidence fields (no enrichment occurs).
    """
    with TemporaryDirectory() as temp_dir:
        # 1. Build a control plane store (SQLite)
        control_plane_store = IngestionConfigRepository(Path(temp_dir) / "config.db")

        # (Do NOT record any snapshots)

        # 2. Build publication contract catalog with empty control plane
        catalog = build_publication_contract_catalog(
            (FINANCE_PACK, UTILITIES_PACK, OVERVIEW_PACK, HOMELAB_PACK),
            publication_relations=PUBLICATION_RELATIONS,
            current_dimension_relations=CURRENT_DIMENSION_RELATIONS,
            current_dimension_contracts=CURRENT_DIMENSION_CONTRACTS,
            control_plane=control_plane_store,
        )

        # 3. Extract the monthly_cashflow contract
        publication_contracts = catalog["publication_contracts"]
        monthly_cashflow = next(
            (c for c in publication_contracts if c.publication_key == "monthly_cashflow"),
            None,
        )
        assert monthly_cashflow is not None

        # 4. Assert confidence fields are None
        assert monthly_cashflow.confidence_verdict is None
        assert monthly_cashflow.freshness_state is None
        assert monthly_cashflow.completeness_pct is None
        assert monthly_cashflow.assessed_at is None


def test_export_contracts_with_multiple_publication_snapshots() -> None:
    """Verify that multiple publications can be enriched with different confidence snapshots.

    This test ensures that the enrichment logic correctly retrieves and applies
    the latest snapshot for each publication independently.
    """
    with TemporaryDirectory() as temp_dir:
        # 1. Build a control plane store
        control_plane_store = IngestionConfigRepository(Path(temp_dir) / "config.db")

        # 2. Record snapshots for two different publications
        now = datetime(2026, 4, 15, 12, 0, 0, tzinfo=UTC)
        snapshots = (
            PublicationConfidenceSnapshotCreate(
                snapshot_id="snap-cashflow",
                publication_key="monthly_cashflow",
                assessed_at=now,
                freshness_state="current",
                completeness_pct=100,
                confidence_verdict="trustworthy",
            ),
            PublicationConfidenceSnapshotCreate(
                snapshot_id="snap-balance",
                publication_key="account_balance_trend",
                assessed_at=now,
                freshness_state="due_soon",
                completeness_pct=85,
                confidence_verdict="degraded",
            ),
        )
        control_plane_store.record_publication_confidence_snapshot(snapshots)

        # 3. Build publication contract catalog
        catalog = build_publication_contract_catalog(
            (FINANCE_PACK, UTILITIES_PACK, OVERVIEW_PACK, HOMELAB_PACK),
            publication_relations=PUBLICATION_RELATIONS,
            current_dimension_relations=CURRENT_DIMENSION_RELATIONS,
            current_dimension_contracts=CURRENT_DIMENSION_CONTRACTS,
            control_plane=control_plane_store,
        )

        # 4. Extract and verify both contracts
        publication_contracts = catalog["publication_contracts"]
        contracts_by_key = {c.publication_key: c for c in publication_contracts}

        monthly_cashflow = contracts_by_key.get("monthly_cashflow")
        assert monthly_cashflow is not None
        assert monthly_cashflow.confidence_verdict == "trustworthy"
        assert monthly_cashflow.freshness_state == "current"
        assert monthly_cashflow.completeness_pct == 100

        account_balance = contracts_by_key.get("account_balance_trend")
        assert account_balance is not None
        assert account_balance.confidence_verdict == "degraded"
        assert account_balance.freshness_state == "due_soon"
        assert account_balance.completeness_pct == 85


def test_export_contracts_gracefully_handles_none_control_plane() -> None:
    """Verify that catalog building works when control_plane is None.

    This test ensures backward compatibility when no control plane is provided.
    """
    # Build publication contract catalog without control plane
    catalog = build_publication_contract_catalog(
        (FINANCE_PACK, UTILITIES_PACK, OVERVIEW_PACK, HOMELAB_PACK),
        publication_relations=PUBLICATION_RELATIONS,
        current_dimension_relations=CURRENT_DIMENSION_RELATIONS,
        current_dimension_contracts=CURRENT_DIMENSION_CONTRACTS,
        control_plane=None,
    )

    # Verify catalog is valid but has no confidence enrichment
    publication_contracts = catalog["publication_contracts"]
    assert len(publication_contracts) > 0

    monthly_cashflow = next(
        (c for c in publication_contracts if c.publication_key == "monthly_cashflow"),
        None,
    )
    assert monthly_cashflow is not None
    assert monthly_cashflow.confidence_verdict is None
    assert monthly_cashflow.freshness_state is None
    assert monthly_cashflow.completeness_pct is None
    assert monthly_cashflow.assessed_at is None
