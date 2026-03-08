"""PLT-18: Run promotion orchestration.

Provides a single supported path to promote a successfully landed run from the
landing layer into the transformation (DuckDB) and reporting layers.

Usage::

    from packages.pipelines.promotion import promote_run, PromotionResult

    result = promote_run(
        run_id="run-abc123",
        account_service=...,
        transformation_service=...,
    )
    # result.facts_loaded, result.marts_refreshed
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.contract_price_service import ContractPriceService
from packages.pipelines.subscription_service import SubscriptionService
from packages.pipelines.transformation_service import TransformationService
from packages.storage.blob import BlobStore
from packages.storage.ingestion_config import (
    IngestionConfigRepository,
    SourceAssetRecord,
)
from packages.storage.run_metadata import RunMetadataStore


_ACCOUNT_TRANSACTION_HEADER = {
    "booked_at",
    "account_id",
    "counterparty_name",
    "amount",
    "currency",
}
_ACCOUNT_TRANSACTION_PUBLICATIONS = [
    "mart_monthly_cashflow",
    "mart_monthly_cashflow_by_counterparty",
    "rpt_current_dim_account",
    "rpt_current_dim_counterparty",
]


@dataclass(frozen=True)
class PromotionResult:
    """Summary of a completed run promotion."""

    run_id: str
    facts_loaded: int
    marts_refreshed: list[str]
    publication_keys: list[str] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str | None = None


def promote_run(
    run_id: str,
    *,
    account_service: AccountTransactionService,
    transformation_service: TransformationService,
) -> PromotionResult:
    """Promote a successfully landed account-transactions run into DuckDB.

    Steps:
    1. Fetch canonical transactions from the landing blob via *account_service*.
    2. Load them into the transformation layer (dim + fact writes, audit record).
    3. Refresh the monthly-cashflow and by-counterparty marts.

    Returns a :class:`PromotionResult` describing what was written.
    If the run did not pass validation the function returns a skipped result
    without touching the analytical store.
    """
    run = account_service.get_run(run_id)
    if not run.passed:
        return PromotionResult(
            run_id=run_id,
            facts_loaded=0,
            marts_refreshed=[],
            publication_keys=[],
            skipped=True,
            skip_reason=f"run status is {run.status.value!r}; only passed runs are promoted",
        )
    if not _ACCOUNT_TRANSACTION_HEADER.issubset(set(run.header)):
        return PromotionResult(
            run_id=run_id,
            facts_loaded=0,
            marts_refreshed=[],
            publication_keys=[],
            skipped=True,
            skip_reason=(
                "run does not match the account-transaction canonical contract"
            ),
        )
    if transformation_service.count_transactions(run_id) > 0:
        marts_refreshed = _refresh_marts(transformation_service)
        return PromotionResult(
            run_id=run_id,
            facts_loaded=0,
            marts_refreshed=marts_refreshed,
            publication_keys=_ACCOUNT_TRANSACTION_PUBLICATIONS.copy(),
            skipped=True,
            skip_reason="run already promoted",
        )

    canonical_rows = account_service.get_canonical_transactions(run_id)
    row_dicts = [
        {
            "booked_at": str(tx.booked_at),
            "account_id": tx.account_id,
            "counterparty_name": tx.counterparty_name,
            "amount": str(tx.amount),
            "currency": tx.currency,
            "description": tx.description or "",
        }
        for tx in canonical_rows
    ]

    facts_loaded = transformation_service.load_transactions(row_dicts, run_id=run_id)

    marts_refreshed = _refresh_marts(transformation_service)

    return PromotionResult(
        run_id=run_id,
        facts_loaded=facts_loaded,
        marts_refreshed=marts_refreshed,
        publication_keys=_ACCOUNT_TRANSACTION_PUBLICATIONS.copy(),
    )


def _refresh_marts(transformation_service: TransformationService) -> list[str]:
    marts_refreshed: list[str] = []
    transformation_service.refresh_monthly_cashflow()
    marts_refreshed.append("mart_monthly_cashflow")
    transformation_service.refresh_monthly_cashflow_by_counterparty()
    marts_refreshed.append("mart_monthly_cashflow_by_counterparty")
    return marts_refreshed


# ---------------------------------------------------------------------------
# Subscription promotion (Phase 2)
# ---------------------------------------------------------------------------

_SUBSCRIPTION_HEADER = {
    "service_name",
    "provider",
    "billing_cycle",
    "amount",
    "currency",
    "start_date",
}
_SUBSCRIPTION_PUBLICATIONS = [
    "mart_subscription_summary",
    "rpt_current_dim_contract",
]
_CONTRACT_PRICE_HEADER = {
    "contract_name",
    "provider",
    "contract_type",
    "price_component",
    "billing_cycle",
    "unit_price",
    "currency",
    "valid_from",
}
_CONTRACT_PRICE_PUBLICATIONS = [
    "mart_contract_price_current",
    "mart_electricity_price_current",
    "rpt_current_dim_contract",
]


def promote_subscription_run(
    run_id: str,
    *,
    subscription_service: SubscriptionService,
    transformation_service: TransformationService,
) -> PromotionResult:
    """Promote a successfully landed subscriptions run into DuckDB.

    Steps:
    1. Fetch canonical subscriptions from the landing blob.
    2. Load them into the transformation layer (dim_contract + fact inserts).
    3. Refresh ``mart_subscription_summary``.

    Returns a :class:`PromotionResult` describing what was written.
    """
    run = subscription_service.get_run(run_id)
    if not run.passed:
        return PromotionResult(
            run_id=run_id,
            facts_loaded=0,
            marts_refreshed=[],
            publication_keys=[],
            skipped=True,
            skip_reason=f"run status is {run.status.value!r}; only passed runs are promoted",
        )

    if transformation_service.count_subscriptions(run_id) > 0:
        transformation_service.refresh_subscription_summary()
        return PromotionResult(
            run_id=run_id,
            facts_loaded=0,
            marts_refreshed=["mart_subscription_summary"],
            publication_keys=_SUBSCRIPTION_PUBLICATIONS.copy(),
            skipped=True,
            skip_reason="run already promoted",
        )

    canonical_rows = subscription_service.get_canonical_subscriptions(run_id)
    row_dicts = [
        {
            "contract_id": sub.contract_id,
            "service_name": sub.service_name,
            "provider": sub.provider,
            "contract_type": "subscription",
            "billing_cycle": sub.billing_cycle,
            "amount": str(sub.amount),
            "currency": sub.currency,
            "start_date": str(sub.start_date),
            "end_date": str(sub.end_date) if sub.end_date else None,
        }
        for sub in canonical_rows
    ]

    facts_loaded = transformation_service.load_subscriptions(row_dicts, run_id=run_id)
    transformation_service.refresh_subscription_summary()

    return PromotionResult(
        run_id=run_id,
        facts_loaded=facts_loaded,
        marts_refreshed=["mart_subscription_summary"],
        publication_keys=_SUBSCRIPTION_PUBLICATIONS.copy(),
    )


def promote_contract_price_run(
    run_id: str,
    *,
    contract_price_service: ContractPriceService,
    transformation_service: TransformationService,
) -> PromotionResult:
    run = contract_price_service.get_run(run_id)
    if not run.passed:
        return PromotionResult(
            run_id=run_id,
            facts_loaded=0,
            marts_refreshed=[],
            publication_keys=[],
            skipped=True,
            skip_reason=f"run status is {run.status.value!r}; only passed runs are promoted",
        )

    if not _CONTRACT_PRICE_HEADER.issubset(set(run.header)):
        return PromotionResult(
            run_id=run_id,
            facts_loaded=0,
            marts_refreshed=[],
            publication_keys=[],
            skipped=True,
            skip_reason="run does not match the contract-price canonical contract",
        )

    if transformation_service.count_contract_prices(run_id) > 0:
        marts_refreshed = _refresh_contract_price_marts(transformation_service)
        return PromotionResult(
            run_id=run_id,
            facts_loaded=0,
            marts_refreshed=marts_refreshed,
            publication_keys=_CONTRACT_PRICE_PUBLICATIONS.copy(),
            skipped=True,
            skip_reason="run already promoted",
        )

    canonical_rows = contract_price_service.get_canonical_contract_prices(run_id)
    row_dicts = [
        {
            "contract_id": row.contract_id,
            "contract_name": row.contract_name,
            "provider": row.provider,
            "contract_type": row.contract_type,
            "price_component": row.price_component,
            "billing_cycle": row.billing_cycle,
            "unit_price": str(row.unit_price),
            "currency": row.currency,
            "quantity_unit": row.quantity_unit,
            "valid_from": str(row.valid_from),
            "valid_to": str(row.valid_to) if row.valid_to else None,
        }
        for row in canonical_rows
    ]

    facts_loaded = transformation_service.load_contract_prices(
        row_dicts,
        run_id=run_id,
    )
    marts_refreshed = _refresh_contract_price_marts(transformation_service)
    return PromotionResult(
        run_id=run_id,
        facts_loaded=facts_loaded,
        marts_refreshed=marts_refreshed,
        publication_keys=_CONTRACT_PRICE_PUBLICATIONS.copy(),
    )


def promote_source_asset_run(
    run_id: str,
    *,
    source_asset: SourceAssetRecord,
    config_repository: IngestionConfigRepository,
    landing_root,
    metadata_repository: RunMetadataStore,
    transformation_service: TransformationService,
    blob_store: BlobStore | None = None,
) -> PromotionResult:
    if source_asset.transformation_package_id is None:
        return PromotionResult(
            run_id=run_id,
            facts_loaded=0,
            marts_refreshed=[],
            publication_keys=[],
            skipped=True,
            skip_reason="source asset does not define a transformation package",
        )

    transformation_package = config_repository.get_transformation_package(
        source_asset.transformation_package_id
    )
    configured_publications = [
        publication.publication_key
        for publication in config_repository.list_publication_definitions(
            transformation_package_id=transformation_package.transformation_package_id
        )
    ]

    if transformation_package.handler_key == "account_transactions":
        result = promote_run(
            run_id,
            account_service=AccountTransactionService(
                landing_root=landing_root,
                metadata_repository=metadata_repository,
                blob_store=blob_store,
            ),
            transformation_service=transformation_service,
        )
        return _apply_publication_selection(
            result,
            supported_publications=_ACCOUNT_TRANSACTION_PUBLICATIONS,
            configured_publications=configured_publications,
        )
    if transformation_package.handler_key == "subscriptions":
        result = promote_subscription_run(
            run_id,
            subscription_service=SubscriptionService(
                landing_root=landing_root,
                metadata_repository=metadata_repository,
                blob_store=blob_store,
            ),
            transformation_service=transformation_service,
        )
        return _apply_publication_selection(
            result,
            supported_publications=_SUBSCRIPTION_PUBLICATIONS,
            configured_publications=configured_publications,
        )
    if transformation_package.handler_key == "contract_prices":
        result = promote_contract_price_run(
            run_id,
            contract_price_service=ContractPriceService(
                landing_root=landing_root,
                metadata_repository=metadata_repository,
                blob_store=blob_store,
            ),
            transformation_service=transformation_service,
        )
        return _apply_publication_selection(
            result,
            supported_publications=_CONTRACT_PRICE_PUBLICATIONS,
            configured_publications=configured_publications,
        )

    raise ValueError(
        f"Unsupported built-in transformation package handler: {transformation_package.handler_key}"
    )


def _apply_publication_selection(
    result: PromotionResult,
    *,
    supported_publications: list[str],
    configured_publications: list[str],
) -> PromotionResult:
    if not configured_publications:
        return replace(result, publication_keys=supported_publications.copy())

    unsupported = sorted(set(configured_publications) - set(supported_publications))
    if unsupported:
        raise ValueError(
            "Configured publication definitions are not supported by the selected transformation package: "
            f"{unsupported}"
        )
    return replace(result, publication_keys=list(configured_publications))


def _refresh_contract_price_marts(
    transformation_service: TransformationService,
) -> list[str]:
    transformation_service.refresh_contract_price_current()
    return [
        "mart_contract_price_current",
        "mart_electricity_price_current",
    ]
