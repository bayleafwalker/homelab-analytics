"""Per-asset run attribution in ``build_source_freshness_views``.

Regression: three bank accounts land into the same ``account_transactions``
dataset. The overview used to list runs by dataset only, so every asset showed
the dataset's newest run (the same ``latest_run_id`` on every /sources row).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Any

from packages.application.use_cases.source_freshness_overview import (
    build_source_freshness_views,
)
from packages.storage.blob import InMemoryBlobStore


@dataclass(frozen=True)
class _Run:
    run_id: str
    dataset_name: str
    status: str
    created_at: datetime
    manifest_path: str


class _ConfigRepo:
    def __init__(self, assets: list[tuple[str, str]]) -> None:
        # (source_asset_id, dataset_name)
        self._assets = assets

    def list_source_assets(self, *, include_archived: bool = False) -> list[Any]:
        return [
            SimpleNamespace(
                source_asset_id=asset_id,
                name=f"Asset {asset_id}",
                dataset_contract_id=f"contract:{dataset}",
            )
            for asset_id, dataset in self._assets
        ]

    def list_source_freshness_configs(self) -> list[Any]:
        return []

    def get_dataset_contract(self, contract_id: str) -> Any:
        return SimpleNamespace(dataset_name=contract_id.split(":", 1)[1])


class _Metadata:
    def __init__(self, runs: list[_Run]) -> None:
        self._runs = sorted(runs, key=lambda r: r.created_at, reverse=True)
        self.calls: list[str | None] = []

    def list_runs(self, *, dataset_name: str | None = None) -> list[_Run]:
        self.calls.append(dataset_name)
        return [r for r in self._runs if r.dataset_name == dataset_name]


def _run(
    blob: InMemoryBlobStore,
    run_id: str,
    dataset: str,
    day: int,
    asset_id: str | None,
    status: str = "landed",
) -> _Run:
    context = {"source_asset_id": asset_id} if asset_id else {}
    path = blob.write_bytes(
        f"manifests/{run_id}.json", json.dumps({"context": context}).encode()
    )
    return _Run(run_id, dataset, status, datetime(2026, 10, day, tzinfo=UTC), path)


def test_assets_sharing_a_dataset_each_get_their_own_latest_run() -> None:
    blob = InMemoryBlobStore()
    runs = [
        _run(blob, "run-personal-1", "account_transactions", 1, "personal"),
        _run(blob, "run-personal-2", "account_transactions", 4, "personal", "rejected"),
        _run(blob, "run-common-1", "account_transactions", 2, "common"),
        _run(blob, "run-revolut-1", "account_transactions", 9, "revolut"),
    ]
    metadata = _Metadata(runs)
    config = _ConfigRepo(
        [
            ("personal", "account_transactions"),
            ("common", "account_transactions"),
            ("revolut", "account_transactions"),
        ]
    )

    views = {
        v.source_asset_id: v
        for v in build_source_freshness_views(
            config, metadata, as_of=date(2026, 10, 18), blob_store=blob
        )
    }

    assert views["personal"].latest_run_id == "run-personal-2"
    assert views["personal"].status == "rejected"
    assert views["personal"].suggested_action == "upload_missing_period"
    assert views["common"].latest_run_id == "run-common-1"
    assert views["revolut"].latest_run_id == "run-revolut-1"
    assert len({v.latest_run_id for v in views.values()}) == 3
    # One listing per dataset, not per asset.
    assert metadata.calls == ["account_transactions"]


def test_asset_without_attributed_runs_reads_as_never_loaded() -> None:
    blob = InMemoryBlobStore()
    metadata = _Metadata(
        [_run(blob, "run-personal-1", "account_transactions", 1, "personal")]
    )
    config = _ConfigRepo(
        [("personal", "account_transactions"), ("common", "account_transactions")]
    )

    views = {
        v.source_asset_id: v
        for v in build_source_freshness_views(
            config, metadata, as_of=date(2026, 10, 18), blob_store=blob
        )
    }

    assert views["personal"].latest_run_id == "run-personal-1"
    assert views["common"].latest_run_id is None
    assert views["common"].landed_at is None


def test_unattributed_runs_count_only_for_a_sole_asset() -> None:
    blob = InMemoryBlobStore()
    metadata = _Metadata(
        [
            _run(blob, "legacy-sub", "subscriptions", 3, None),
            _run(blob, "legacy-acct", "account_transactions", 5, None),
        ]
    )
    config = _ConfigRepo(
        [
            ("subs", "subscriptions"),
            ("personal", "account_transactions"),
            ("common", "account_transactions"),
        ]
    )

    views = {
        v.source_asset_id: v
        for v in build_source_freshness_views(
            config, metadata, as_of=date(2026, 10, 18), blob_store=blob
        )
    }

    assert views["subs"].latest_run_id == "legacy-sub"
    assert views["personal"].latest_run_id is None
    assert views["common"].latest_run_id is None


def test_unreadable_manifest_is_treated_as_unattributed() -> None:
    blob = InMemoryBlobStore()
    missing = _Run(
        "run-x", "subscriptions", "landed", datetime(2026, 10, 1, tzinfo=UTC), "memory://gone"
    )
    views = build_source_freshness_views(
        _ConfigRepo([("subs", "subscriptions")]),
        _Metadata([missing]),
        as_of=date(2026, 10, 18),
        blob_store=blob,
    )
    assert views[0].latest_run_id == "run-x"


def test_without_blob_store_every_dataset_run_is_used() -> None:
    blob = InMemoryBlobStore()
    metadata = _Metadata(
        [_run(blob, "run-common-1", "account_transactions", 2, "common")]
    )
    views = build_source_freshness_views(
        _ConfigRepo([("personal", "account_transactions")]),
        metadata,
        as_of=date(2026, 10, 18),
    )
    assert views[0].latest_run_id == "run-common-1"


def test_monthly_source_that_landed_its_expected_period_reads_current() -> None:
    """/sources derives the period a run covers the same way confidence does."""
    from packages.platform.source_freshness import SourceFreshnessState
    from packages.storage.ingestion_catalog import SourceFreshnessConfigCreate

    monthly = SourceFreshnessConfigCreate(
        source_asset_id="personal",
        acquisition_mode="manual_export",
        expected_frequency="monthly",
        coverage_kind="rolling_period",
        due_day_of_month=5,
        expected_window_days=3,
        freshness_sla_days=40,
        sensitivity_class="financial",
        reminder_channel="dashboard",
        requires_human_action=True,
    )

    class _Configured(_ConfigRepo):
        def list_source_freshness_configs(self) -> list[Any]:
            return [monthly]

    blob = InMemoryBlobStore()
    config = _Configured([("personal", "account_transactions")])

    landed_in_october = _Metadata(
        [_run(blob, "run-1", "account_transactions", 2, "personal")]
    )
    (view,) = build_source_freshness_views(
        config, landed_in_october, as_of=date(2026, 10, 18), blob_store=blob
    )
    assert view.freshness_state == SourceFreshnessState.CURRENT
    assert view.covered_through == date(2026, 9, 30)

    (later,) = build_source_freshness_views(
        config, landed_in_october, as_of=date(2026, 11, 18), blob_store=blob
    )
    assert later.freshness_state == SourceFreshnessState.OVERDUE
