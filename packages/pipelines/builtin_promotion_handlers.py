from __future__ import annotations

from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.builtin_packages import (
    get_builtin_transformation_package_spec,
    get_builtin_transformation_package_spec_by_handler_key,
)
from packages.pipelines.contract_price_service import ContractPriceService
from packages.pipelines.promotion_registry import (
    BuiltinPromotionHandler,
    PromotionRuntime,
)
from packages.pipelines.promotion_types import PromotionResult
from packages.pipelines.subscription_service import SubscriptionService
from packages.pipelines.transformation_service import TransformationService
from packages.pipelines.utility_bill_service import UtilityBillService
from packages.pipelines.utility_usage_service import UtilityUsageService

_ACCOUNT_TRANSACTION_HEADER = {
    "booked_at",
    "account_id",
    "counterparty_name",
    "amount",
    "currency",
}
_ACCOUNT_TRANSACTION_PUBLICATIONS = list(
    get_builtin_transformation_package_spec(
        "builtin_account_transactions"
    ).publication_keys
)
_SUBSCRIPTION_PUBLICATIONS = list(
    get_builtin_transformation_package_spec("builtin_subscriptions").publication_keys
)
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
_CONTRACT_PRICE_PUBLICATIONS = list(
    get_builtin_transformation_package_spec(
        "builtin_contract_prices"
    ).publication_keys
)
_UTILITY_USAGE_HEADER = {
    "meter_id",
    "meter_name",
    "utility_type",
    "usage_start",
    "usage_end",
    "usage_quantity",
    "usage_unit",
}
_UTILITY_BILL_HEADER = {
    "meter_id",
    "meter_name",
    "utility_type",
    "billing_period_start",
    "billing_period_end",
    "billed_amount",
    "currency",
}
_UTILITY_PUBLICATIONS = list(
    get_builtin_transformation_package_spec("builtin_utility_usage").publication_keys
)


def _skipped_result(
    run_id: str,
    *,
    publication_keys: list[str] | None = None,
    skip_reason: str,
    marts_refreshed: list[str] | None = None,
) -> PromotionResult:
    return PromotionResult(
        run_id=run_id,
        facts_loaded=0,
        marts_refreshed=marts_refreshed or [],
        publication_keys=publication_keys or [],
        skipped=True,
        skip_reason=skip_reason,
    )


def promote_run(
    run_id: str,
    *,
    account_service: AccountTransactionService,
    transformation_service: TransformationService,
) -> PromotionResult:
    """Promote a successfully landed account-transactions run into DuckDB."""

    run = account_service.get_run(run_id)
    if not run.passed:
        return _skipped_result(
            run_id,
            skip_reason=(
                f"run status is {run.status.value!r}; only passed runs are promoted"
            ),
        )
    if not _ACCOUNT_TRANSACTION_HEADER.issubset(set(run.header)):
        return _skipped_result(
            run_id,
            skip_reason="run does not match the account-transaction canonical contract",
        )
    if transformation_service.count_transactions(run_id) > 0:
        marts_refreshed = _refresh_account_transaction_marts(transformation_service)
        return _skipped_result(
            run_id,
            publication_keys=_ACCOUNT_TRANSACTION_PUBLICATIONS.copy(),
            marts_refreshed=marts_refreshed,
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

    facts_loaded = transformation_service.load_transactions(
        row_dicts,
        run_id=run_id,
        source_system=run.source_name,
    )
    marts_refreshed = _refresh_account_transaction_marts(transformation_service)
    return PromotionResult(
        run_id=run_id,
        facts_loaded=facts_loaded,
        marts_refreshed=marts_refreshed,
        publication_keys=_ACCOUNT_TRANSACTION_PUBLICATIONS.copy(),
    )


def promote_subscription_run(
    run_id: str,
    *,
    subscription_service: SubscriptionService,
    transformation_service: TransformationService,
) -> PromotionResult:
    run = subscription_service.get_run(run_id)
    if not run.passed:
        return _skipped_result(
            run_id,
            skip_reason=(
                f"run status is {run.status.value!r}; only passed runs are promoted"
            ),
        )

    if transformation_service.count_subscriptions(run_id) > 0:
        transformation_service.refresh_subscription_summary()
        return _skipped_result(
            run_id,
            publication_keys=_SUBSCRIPTION_PUBLICATIONS.copy(),
            marts_refreshed=["mart_subscription_summary"],
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

    facts_loaded = transformation_service.load_subscriptions(
        row_dicts,
        run_id=run_id,
        source_system=run.source_name,
    )
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
        return _skipped_result(
            run_id,
            skip_reason=(
                f"run status is {run.status.value!r}; only passed runs are promoted"
            ),
        )

    if not _CONTRACT_PRICE_HEADER.issubset(set(run.header)):
        return _skipped_result(
            run_id,
            skip_reason="run does not match the contract-price canonical contract",
        )

    if transformation_service.count_contract_prices(run_id) > 0:
        marts_refreshed = _refresh_contract_price_marts(transformation_service)
        return _skipped_result(
            run_id,
            publication_keys=_CONTRACT_PRICE_PUBLICATIONS.copy(),
            marts_refreshed=marts_refreshed,
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
        source_system=run.source_name,
    )
    marts_refreshed = _refresh_contract_price_marts(transformation_service)
    return PromotionResult(
        run_id=run_id,
        facts_loaded=facts_loaded,
        marts_refreshed=marts_refreshed,
        publication_keys=_CONTRACT_PRICE_PUBLICATIONS.copy(),
    )


def promote_utility_usage_run(
    run_id: str,
    *,
    utility_usage_service: UtilityUsageService,
    transformation_service: TransformationService,
) -> PromotionResult:
    run = utility_usage_service.get_run(run_id)
    if not run.passed:
        return _skipped_result(
            run_id,
            skip_reason=(
                f"run status is {run.status.value!r}; only passed runs are promoted"
            ),
        )

    if not _UTILITY_USAGE_HEADER.issubset(set(run.header)):
        return _skipped_result(
            run_id,
            skip_reason="run does not match the utility-usage canonical contract",
        )

    if transformation_service.count_utility_usage(run_id) > 0:
        transformation_service.refresh_utility_cost_summary()
        return _skipped_result(
            run_id,
            publication_keys=_UTILITY_PUBLICATIONS.copy(),
            marts_refreshed=["mart_utility_cost_summary"],
            skip_reason="run already promoted",
        )

    canonical_rows = utility_usage_service.get_canonical_utility_usage(run_id)
    row_dicts = [
        {
            "meter_id": row.meter_id,
            "meter_name": row.meter_name,
            "utility_type": row.utility_type,
            "location": row.location,
            "usage_start": str(row.usage_start),
            "usage_end": str(row.usage_end),
            "usage_quantity": str(row.usage_quantity),
            "usage_unit": row.usage_unit,
            "reading_source": row.reading_source,
        }
        for row in canonical_rows
    ]

    facts_loaded = transformation_service.load_utility_usage(
        row_dicts,
        run_id=run_id,
        source_system=run.source_name,
    )
    transformation_service.refresh_utility_cost_summary()

    return PromotionResult(
        run_id=run_id,
        facts_loaded=facts_loaded,
        marts_refreshed=["mart_utility_cost_summary"],
        publication_keys=_UTILITY_PUBLICATIONS.copy(),
    )


def promote_utility_bill_run(
    run_id: str,
    *,
    utility_bill_service: UtilityBillService,
    transformation_service: TransformationService,
) -> PromotionResult:
    run = utility_bill_service.get_run(run_id)
    if not run.passed:
        return _skipped_result(
            run_id,
            skip_reason=(
                f"run status is {run.status.value!r}; only passed runs are promoted"
            ),
        )

    if not _UTILITY_BILL_HEADER.issubset(set(run.header)):
        return _skipped_result(
            run_id,
            skip_reason="run does not match the utility-bill canonical contract",
        )

    if transformation_service.count_bills(run_id) > 0:
        transformation_service.refresh_utility_cost_summary()
        return _skipped_result(
            run_id,
            publication_keys=_UTILITY_PUBLICATIONS.copy(),
            marts_refreshed=["mart_utility_cost_summary"],
            skip_reason="run already promoted",
        )

    canonical_rows = utility_bill_service.get_canonical_utility_bills(run_id)
    row_dicts = [
        {
            "meter_id": row.meter_id,
            "meter_name": row.meter_name,
            "provider": row.provider,
            "utility_type": row.utility_type,
            "location": row.location,
            "billing_period_start": str(row.billing_period_start),
            "billing_period_end": str(row.billing_period_end),
            "billed_amount": str(row.billed_amount),
            "currency": row.currency,
            "billed_quantity": (
                str(row.billed_quantity) if row.billed_quantity is not None else None
            ),
            "usage_unit": row.usage_unit,
            "invoice_date": str(row.invoice_date) if row.invoice_date else None,
        }
        for row in canonical_rows
    ]

    facts_loaded = transformation_service.load_bills(
        row_dicts,
        run_id=run_id,
        source_system=run.source_name,
    )
    transformation_service.refresh_utility_cost_summary()

    return PromotionResult(
        run_id=run_id,
        facts_loaded=facts_loaded,
        marts_refreshed=["mart_utility_cost_summary"],
        publication_keys=_UTILITY_PUBLICATIONS.copy(),
    )


def _run_account_transaction_promotion(runtime: PromotionRuntime) -> PromotionResult:
    return promote_run(
        runtime.run_id,
        account_service=AccountTransactionService(
            landing_root=runtime.landing_root,
            metadata_repository=runtime.metadata_repository,
            blob_store=runtime.blob_store,
        ),
        transformation_service=runtime.transformation_service,  # type: ignore[arg-type]
    )


def _run_subscription_promotion(runtime: PromotionRuntime) -> PromotionResult:
    return promote_subscription_run(
        runtime.run_id,
        subscription_service=SubscriptionService(
            landing_root=runtime.landing_root,
            metadata_repository=runtime.metadata_repository,
            blob_store=runtime.blob_store,
        ),
        transformation_service=runtime.transformation_service,  # type: ignore[arg-type]
    )


def _run_contract_price_promotion(runtime: PromotionRuntime) -> PromotionResult:
    return promote_contract_price_run(
        runtime.run_id,
        contract_price_service=ContractPriceService(
            landing_root=runtime.landing_root,
            metadata_repository=runtime.metadata_repository,
            blob_store=runtime.blob_store,
        ),
        transformation_service=runtime.transformation_service,  # type: ignore[arg-type]
    )


def _run_utility_usage_promotion(runtime: PromotionRuntime) -> PromotionResult:
    return promote_utility_usage_run(
        runtime.run_id,
        utility_usage_service=UtilityUsageService(
            landing_root=runtime.landing_root,
            metadata_repository=runtime.metadata_repository,
            blob_store=runtime.blob_store,
        ),
        transformation_service=runtime.transformation_service,  # type: ignore[arg-type]
    )


def _run_utility_bill_promotion(runtime: PromotionRuntime) -> PromotionResult:
    return promote_utility_bill_run(
        runtime.run_id,
        utility_bill_service=UtilityBillService(
            landing_root=runtime.landing_root,
            metadata_repository=runtime.metadata_repository,
            blob_store=runtime.blob_store,
        ),
        transformation_service=runtime.transformation_service,  # type: ignore[arg-type]
    )


_BUILTIN_PROMOTION_HANDLERS = {
    handler.handler_key: handler
    for handler in (
        BuiltinPromotionHandler(
            package_spec=get_builtin_transformation_package_spec_by_handler_key(
                "account_transactions"
            ),
            runner=_run_account_transaction_promotion,
        ),
        BuiltinPromotionHandler(
            package_spec=get_builtin_transformation_package_spec_by_handler_key(
                "subscriptions"
            ),
            runner=_run_subscription_promotion,
        ),
        BuiltinPromotionHandler(
            package_spec=get_builtin_transformation_package_spec_by_handler_key(
                "contract_prices"
            ),
            runner=_run_contract_price_promotion,
        ),
        BuiltinPromotionHandler(
            package_spec=get_builtin_transformation_package_spec_by_handler_key(
                "utility_usage"
            ),
            runner=_run_utility_usage_promotion,
        ),
        BuiltinPromotionHandler(
            package_spec=get_builtin_transformation_package_spec_by_handler_key(
                "utility_bills"
            ),
            runner=_run_utility_bill_promotion,
        ),
    )
}


def get_builtin_promotion_handler(handler_key: str) -> BuiltinPromotionHandler:
    try:
        return _BUILTIN_PROMOTION_HANDLERS[handler_key]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported built-in transformation package handler: {handler_key}"
        ) from exc


def _refresh_account_transaction_marts(
    transformation_service: TransformationService,
) -> list[str]:
    marts_refreshed: list[str] = []
    transformation_service.refresh_monthly_cashflow()
    marts_refreshed.append("mart_monthly_cashflow")
    transformation_service.refresh_monthly_cashflow_by_counterparty()
    marts_refreshed.append("mart_monthly_cashflow_by_counterparty")
    return marts_refreshed


def _refresh_contract_price_marts(
    transformation_service: TransformationService,
) -> list[str]:
    transformation_service.refresh_contract_price_current()
    return [
        "mart_contract_price_current",
        "mart_electricity_price_current",
    ]
