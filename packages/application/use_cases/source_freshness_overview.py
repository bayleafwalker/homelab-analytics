"""Per-source freshness views assembled from the control plane and run metadata.

Shared by ``GET /control/source-freshness`` and the morning brief so both
surfaces report the same state and the same suggested remediation for a
source. Freshness is computed, not stored (see
``docs/product/source-freshness-workflow.md``).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Protocol

from packages.platform.source_freshness import (
    SourceFreshnessRunObservation,
    SourceFreshnessState,
    SourceFreshnessView,
    evaluate_source_freshness,
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
) -> list[SourceFreshnessView]:
    """Evaluate freshness for every non-archived source asset.

    ``config_repository`` must provide ``list_source_assets``,
    ``list_source_freshness_configs`` and ``get_dataset_contract``;
    ``metadata_repository`` must provide ``list_runs`` (newest first).
    """
    source_assets = config_repository.list_source_assets(include_archived=False)
    freshness_configs = {
        cfg.source_asset_id: cfg
        for cfg in config_repository.list_source_freshness_configs()
    }
    views: list[SourceFreshnessView] = []
    for asset in source_assets:
        dataset_contract = config_repository.get_dataset_contract(
            asset.dataset_contract_id
        )
        dataset_name = dataset_contract.dataset_name
        runs = list(metadata_repository.list_runs(dataset_name=dataset_name))
        observations = [
            SourceFreshnessRunObservation(
                status=str(run.status),
                observed_at=run.created_at,
                covered_from=None,
                covered_through=None,
                dataset_name=dataset_name,
            )
            for run in runs
        ]
        config = freshness_configs.get(asset.source_asset_id)
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
