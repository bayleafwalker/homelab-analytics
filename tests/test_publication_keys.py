"""PublicationKeyResolver: one mapping between contract keys and relation names."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from packages.pipelines.composition.builtin_packs import BUILTIN_CAPABILITY_PACKS
from packages.pipelines.publication_confidence_service import (
    compute_and_record_publication_confidence,
)
from packages.platform.publication_confidence import get_latest_publication_confidence
from packages.platform.publication_keys import (
    PublicationKeyResolver,
    pack_publication_relation_name,
)
from packages.storage.control_plane import (
    PublicationConfidenceSnapshotCreate,
    SourceLineageCreate,
)
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.ingestion_config import IngestionConfigRepository

AS_OF = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
def resolver() -> PublicationKeyResolver:
    return PublicationKeyResolver.from_capability_packs(BUILTIN_CAPABILITY_PACKS)


@pytest.fixture
def control_plane(tmp_path: Path) -> IngestionConfigRepository:
    return IngestionConfigRepository(tmp_path / "config.db")


def _snapshot(key: str, *, snapshot_id: str, assessed_at: datetime, verdict: str):
    return PublicationConfidenceSnapshotCreate(
        snapshot_id=snapshot_id,
        publication_key=key,
        assessed_at=assessed_at,
        freshness_state="current",
        completeness_pct=100,
        confidence_verdict=verdict,
    )


def test_resolver_maps_both_namespaces_to_the_relation_name(
    resolver: PublicationKeyResolver,
) -> None:
    assert resolver.snapshot_key("monthly_cashflow") == "mart_monthly_cashflow"
    assert resolver.snapshot_key("mart_monthly_cashflow") == "mart_monthly_cashflow"
    assert resolver.contract_key("mart_monthly_cashflow") == "monthly_cashflow"
    assert resolver.contract_key("monthly_cashflow") == "monthly_cashflow"
    assert resolver.snapshot_lookup_keys("monthly_cashflow") == (
        "mart_monthly_cashflow",
        "monthly_cashflow",
    )


def test_resolver_leaves_non_pack_relations_unchanged(
    resolver: PublicationKeyResolver,
) -> None:
    for relation in ("mart_homelab_roi", "rpt_current_dim_account", "unknown_key"):
        assert resolver.snapshot_key(relation) == relation
        assert resolver.contract_key(relation) == relation
        assert resolver.snapshot_lookup_keys(relation) == (relation,)


def test_resolver_covers_every_builtin_pack_publication(
    resolver: PublicationKeyResolver,
) -> None:
    for pack in BUILTIN_CAPABILITY_PACKS:
        for publication in pack.publications:
            relation = pack_publication_relation_name(publication)
            assert resolver.snapshot_key(publication.key) == relation
            assert resolver.contract_key(relation) == publication.key


def test_latest_confidence_reads_canonical_and_legacy_snapshots(
    resolver: PublicationKeyResolver,
    control_plane: IngestionConfigRepository,
) -> None:
    control_plane.record_publication_confidence_snapshot(
        (
            _snapshot(
                "monthly_cashflow",
                snapshot_id="legacy",
                assessed_at=AS_OF - timedelta(days=1),
                verdict="degraded",
            ),
        )
    )
    legacy = get_latest_publication_confidence(
        "monthly_cashflow", control_plane, key_resolver=resolver
    )
    assert legacy is not None
    assert legacy.snapshot_id == "legacy"
    assert legacy.publication_key == "mart_monthly_cashflow"

    control_plane.record_publication_confidence_snapshot(
        (
            _snapshot(
                "mart_monthly_cashflow",
                snapshot_id="canonical",
                assessed_at=AS_OF,
                verdict="trustworthy",
            ),
        )
    )
    for key in ("monthly_cashflow", "mart_monthly_cashflow"):
        latest = get_latest_publication_confidence(key, control_plane, key_resolver=resolver)
        assert latest is not None
        assert latest.snapshot_id == "canonical"


def test_recording_confidence_canonicalizes_contract_keys(
    resolver: PublicationKeyResolver,
    control_plane: IngestionConfigRepository,
) -> None:
    control_plane.record_source_lineage(
        (
            SourceLineageCreate(
                lineage_id="lin-1",
                input_run_id="run-1",
                source_run_id="run-1",
                target_layer="reporting",
                target_name="mart_monthly_cashflow",
                target_kind="mart",
                source_system="bank",
            ),
        )
    )

    snapshot = compute_and_record_publication_confidence(
        "monthly_cashflow",
        control_plane,
        DuckDBStore.memory(),
        as_of=AS_OF,
        key_resolver=resolver,
    )

    assert snapshot.publication_key == "mart_monthly_cashflow"
    # Lineage was read under the relation name, so the source contributed.
    assert snapshot.contributing_run_ids == ["run-1"]
    assert [
        record.publication_key for record in control_plane.list_publication_confidence_snapshots()
    ] == ["mart_monthly_cashflow"]
