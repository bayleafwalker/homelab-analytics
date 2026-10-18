"""Per-source freshness views assembled from the control plane and run metadata.

Shared by ``GET /control/source-freshness`` and the morning brief so both
surfaces report the same state and the same suggested remediation for a
source. Freshness is computed, not stored (see
``docs/product/source-freshness-workflow.md``).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any, Protocol

from packages.pipelines.run_context import read_run_context
from packages.platform.source_freshness import (
    SourceFreshnessState,
    SourceFreshnessView,
    evaluate_source_freshness,
    run_observation,
)


class _RunListing(Protocol):
    def list_runs(self, *, dataset_name: str | None = None) -> Any: ...


def suggested_freshness_action(
    state: SourceFreshnessState, latest_status: str | None
) -> str:
    """Return the next operator action for a source in ``state``."""
    if state == SourceFreshnessState.PARSE_FAILED:
        return "retry"
    if state in (SourceFreshnessState.OVERDUE, SourceFreshnessState.MISSING_PERIOD):
        return "upload_missing_period"
    if latest_status == "rejected":
        return "upload_missing_period"
    return "none"


def build_source_freshness_views(
    config_repository: Any,
    metadata_repository: _RunListing,
    *,
    as_of: date,
    blob_store: Any = None,
) -> list[SourceFreshnessView]:
    """Evaluate freshness for every non-archived source asset.

    ``config_repository`` must provide ``list_source_assets``,
    ``list_source_freshness_configs`` and ``get_dataset_contract``;
    ``metadata_repository`` must provide ``list_runs`` (newest first).

    Several source assets can land into the same dataset (three bank
    accounts all feed ``account_transactions``). Runs are attributed to an
    asset through the ``source_asset_id`` recorded in each run's manifest
    context, read from ``blob_store``. A run with no recorded asset is only
    attributed when its dataset has exactly one source asset; without a
    ``blob_store`` every run of the dataset is used (single-asset behaviour).
    """
    source_assets = config_repository.list_source_assets(include_archived=False)
    freshness_configs = {
        cfg.source_asset_id: cfg
        for cfg in config_repository.list_source_freshness_configs()
    }
    dataset_by_asset: dict[str, str] = {}
    assets_by_dataset: dict[str, list[str]] = defaultdict(list)
    for asset in source_assets:
        dataset_contract = config_repository.get_dataset_contract(
            asset.dataset_contract_id
        )
        dataset_by_asset[asset.source_asset_id] = dataset_contract.dataset_name
        assets_by_dataset[dataset_contract.dataset_name].append(asset.source_asset_id)

    runs_by_dataset: dict[str, list[Any]] = {}
    run_asset_ids: dict[str, str | None] = {}

    def _dataset_runs(dataset_name: str) -> list[Any]:
        if dataset_name not in runs_by_dataset:
            runs = list(metadata_repository.list_runs(dataset_name=dataset_name))
            runs_by_dataset[dataset_name] = runs
            if blob_store is not None:
                for run in runs:
                    run_asset_ids[run.run_id] = _run_source_asset_id(run, blob_store)
        return runs_by_dataset[dataset_name]

    views: list[SourceFreshnessView] = []
    for asset in source_assets:
        dataset_name = dataset_by_asset[asset.source_asset_id]
        dataset_runs = _dataset_runs(dataset_name)
        if blob_store is None:
            runs = dataset_runs
        else:
            sole_asset = len(assets_by_dataset[dataset_name]) == 1
            runs = [
                run
                for run in dataset_runs
                if run_asset_ids.get(run.run_id) == asset.source_asset_id
                or (sole_asset and run_asset_ids.get(run.run_id) is None)
            ]
        config = freshness_configs.get(asset.source_asset_id)
        observations = [
            run_observation(
                config,
                status=str(run.status),
                observed_at=run.created_at,
                dataset_name=dataset_name,
                as_of=as_of,
            )
            for run in runs
        ]
        assessment = evaluate_source_freshness(config, observations, as_of=as_of)
        latest_run = runs[0] if runs else None
        latest_status = str(latest_run.status) if latest_run else None
        views.append(
            SourceFreshnessView(
                source_asset_id=asset.source_asset_id,
                dataset_name=dataset_name,
                name=asset.name,
                freshness_state=assessment.state,
                latest_run_id=latest_run.run_id if latest_run else None,
                status=latest_status,
                landed_at=latest_run.created_at if latest_run else None,
                next_expected_at=assessment.next_expected_at,
                covered_through=assessment.covered_through,
                suggested_action=suggested_freshness_action(
                    assessment.state, latest_status
                ),
            )
        )
    return views


def _run_source_asset_id(run: Any, blob_store: Any) -> str | None:
    """Return the source asset a run was landed for, or ``None`` if unrecorded."""
    try:
        context = read_run_context(blob_store, run.manifest_path)
    except (KeyError, OSError, ValueError):
        return None
    return context.source_asset_id if context is not None else None
