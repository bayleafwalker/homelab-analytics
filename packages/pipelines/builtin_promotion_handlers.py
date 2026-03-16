from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.builtin_packages import (
    BuiltinTransformationPackageSpec,
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


@dataclass(frozen=True)
class BuiltinPromotionFlowSpec:
    package_spec: BuiltinTransformationPackageSpec
    build_runtime_service: Callable[[PromotionRuntime], Any]
    get_run: Callable[[Any, str], Any]
    get_canonical_rows: Callable[[Any, str], list[Any]]
    serialize_row: Callable[[Any], dict[str, Any]]
    count_existing: Callable[[TransformationService, str], int]
    load_rows: Callable[[TransformationService, list[dict[str, Any]], str, str], int]
    required_header: set[str] | None = None
    contract_mismatch_reason: str | None = None

    @property
    def publication_keys(self) -> list[str]:
        return list(self.package_spec.publication_keys)

    @property
    def refresh_publication_keys(self) -> list[str]:
        return list(self.package_spec.refresh_publication_keys)


_ACCOUNT_TRANSACTION_HEADER = {
    "booked_at",
    "account_id",
    "counterparty_name",
    "amount",
    "currency",
}
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


def _load_transaction_rows(
    transformation_service: TransformationService,
    rows: list[dict[str, Any]],
    run_id: str,
    source_name: str,
) -> int:
    return transformation_service.load_transactions(
        rows,
        run_id=run_id,
        source_system=source_name,
    )


def _load_subscription_rows(
    transformation_service: TransformationService,
    rows: list[dict[str, Any]],
    run_id: str,
    source_name: str,
) -> int:
    return transformation_service.load_subscriptions(
        rows,
        run_id=run_id,
        source_system=source_name,
    )


def _load_contract_price_rows(
    transformation_service: TransformationService,
    rows: list[dict[str, Any]],
    run_id: str,
    source_name: str,
) -> int:
    return transformation_service.load_contract_prices(
        rows,
        run_id=run_id,
        source_system=source_name,
    )


def _load_utility_usage_rows(
    transformation_service: TransformationService,
    rows: list[dict[str, Any]],
    run_id: str,
    source_name: str,
) -> int:
    return transformation_service.load_utility_usage(
        rows,
        run_id=run_id,
        source_system=source_name,
    )


def _load_utility_bill_rows(
    transformation_service: TransformationService,
    rows: list[dict[str, Any]],
    run_id: str,
    source_name: str,
) -> int:
    return transformation_service.load_bills(
        rows,
        run_id=run_id,
        source_system=source_name,
    )


_ACCOUNT_TRANSACTION_FLOW = BuiltinPromotionFlowSpec(
    package_spec=get_builtin_transformation_package_spec("builtin_account_transactions"),
    build_runtime_service=lambda runtime: AccountTransactionService(
        landing_root=runtime.landing_root,
        metadata_repository=runtime.metadata_repository,
        blob_store=runtime.blob_store,
    ),
    get_run=lambda service, run_id: service.get_run(run_id),
    get_canonical_rows=lambda service, run_id: service.get_canonical_transactions(run_id),
    serialize_row=lambda row: {
        "booked_at": str(row.booked_at),
        "account_id": row.account_id,
        "counterparty_name": row.counterparty_name,
        "amount": str(row.amount),
        "currency": row.currency,
        "description": row.description or "",
    },
    count_existing=lambda transformation_service, run_id: transformation_service.count_transactions(
        run_id
    ),
    load_rows=_load_transaction_rows,
    required_header=_ACCOUNT_TRANSACTION_HEADER,
    contract_mismatch_reason="run does not match the account-transaction canonical contract",
)

_SUBSCRIPTION_FLOW = BuiltinPromotionFlowSpec(
    package_spec=get_builtin_transformation_package_spec("builtin_subscriptions"),
    build_runtime_service=lambda runtime: SubscriptionService(
        landing_root=runtime.landing_root,
        metadata_repository=runtime.metadata_repository,
        blob_store=runtime.blob_store,
    ),
    get_run=lambda service, run_id: service.get_run(run_id),
    get_canonical_rows=lambda service, run_id: service.get_canonical_subscriptions(run_id),
    serialize_row=lambda row: {
        "contract_id": row.contract_id,
        "service_name": row.service_name,
        "provider": row.provider,
        "contract_type": "subscription",
        "billing_cycle": row.billing_cycle,
        "amount": str(row.amount),
        "currency": row.currency,
        "start_date": str(row.start_date),
        "end_date": str(row.end_date) if row.end_date else None,
    },
    count_existing=lambda transformation_service, run_id: transformation_service.count_subscriptions(
        run_id
    ),
    load_rows=_load_subscription_rows,
)

_CONTRACT_PRICE_FLOW = BuiltinPromotionFlowSpec(
    package_spec=get_builtin_transformation_package_spec("builtin_contract_prices"),
    build_runtime_service=lambda runtime: ContractPriceService(
        landing_root=runtime.landing_root,
        metadata_repository=runtime.metadata_repository,
        blob_store=runtime.blob_store,
    ),
    get_run=lambda service, run_id: service.get_run(run_id),
    get_canonical_rows=lambda service, run_id: service.get_canonical_contract_prices(run_id),
    serialize_row=lambda row: {
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
    },
    count_existing=lambda transformation_service, run_id: transformation_service.count_contract_prices(
        run_id
    ),
    load_rows=_load_contract_price_rows,
    required_header=_CONTRACT_PRICE_HEADER,
    contract_mismatch_reason="run does not match the contract-price canonical contract",
)

_UTILITY_USAGE_FLOW = BuiltinPromotionFlowSpec(
    package_spec=get_builtin_transformation_package_spec("builtin_utility_usage"),
    build_runtime_service=lambda runtime: UtilityUsageService(
        landing_root=runtime.landing_root,
        metadata_repository=runtime.metadata_repository,
        blob_store=runtime.blob_store,
    ),
    get_run=lambda service, run_id: service.get_run(run_id),
    get_canonical_rows=lambda service, run_id: service.get_canonical_utility_usage(run_id),
    serialize_row=lambda row: {
        "meter_id": row.meter_id,
        "meter_name": row.meter_name,
        "utility_type": row.utility_type,
        "location": row.location,
        "usage_start": str(row.usage_start),
        "usage_end": str(row.usage_end),
        "usage_quantity": str(row.usage_quantity),
        "usage_unit": row.usage_unit,
        "reading_source": row.reading_source,
    },
    count_existing=lambda transformation_service, run_id: transformation_service.count_utility_usage(
        run_id
    ),
    load_rows=_load_utility_usage_rows,
    required_header=_UTILITY_USAGE_HEADER,
    contract_mismatch_reason="run does not match the utility-usage canonical contract",
)

_UTILITY_BILL_FLOW = BuiltinPromotionFlowSpec(
    package_spec=get_builtin_transformation_package_spec("builtin_utility_bills"),
    build_runtime_service=lambda runtime: UtilityBillService(
        landing_root=runtime.landing_root,
        metadata_repository=runtime.metadata_repository,
        blob_store=runtime.blob_store,
    ),
    get_run=lambda service, run_id: service.get_run(run_id),
    get_canonical_rows=lambda service, run_id: service.get_canonical_utility_bills(run_id),
    serialize_row=lambda row: {
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
    },
    count_existing=lambda transformation_service, run_id: transformation_service.count_bills(
        run_id
    ),
    load_rows=_load_utility_bill_rows,
    required_header=_UTILITY_BILL_HEADER,
    contract_mismatch_reason="run does not match the utility-bill canonical contract",
)

_BUILTIN_PROMOTION_FLOWS = (
    _ACCOUNT_TRANSACTION_FLOW,
    _SUBSCRIPTION_FLOW,
    _CONTRACT_PRICE_FLOW,
    _UTILITY_USAGE_FLOW,
    _UTILITY_BILL_FLOW,
)
def _promote_with_flow(
    run_id: str,
    *,
    service: Any,
    transformation_service: TransformationService,
    flow: BuiltinPromotionFlowSpec,
) -> PromotionResult:
    run = flow.get_run(service, run_id)
    if not run.passed:
        return _skipped_result(
            run_id,
            skip_reason=(
                f"run status is {run.status.value!r}; only passed runs are promoted"
            ),
        )
    if flow.required_header and not flow.required_header.issubset(set(run.header)):
        return _skipped_result(
            run_id,
            skip_reason=flow.contract_mismatch_reason
            or "run does not match the canonical contract",
        )
    if flow.count_existing(transformation_service, run_id) > 0:
        marts_refreshed = transformation_service.refresh_publications(
            flow.refresh_publication_keys
        )
        return _skipped_result(
            run_id,
            publication_keys=flow.publication_keys,
            marts_refreshed=marts_refreshed,
            skip_reason="run already promoted",
        )

    row_dicts = [
        flow.serialize_row(row) for row in flow.get_canonical_rows(service, run_id)
    ]
    facts_loaded = flow.load_rows(
        transformation_service,
        row_dicts,
        run_id,
        run.source_name,
    )
    marts_refreshed = transformation_service.refresh_publications(
        flow.refresh_publication_keys
    )
    return PromotionResult(
        run_id=run_id,
        facts_loaded=facts_loaded,
        marts_refreshed=marts_refreshed,
        publication_keys=flow.publication_keys,
    )


def promote_run(
    run_id: str,
    *,
    account_service: AccountTransactionService,
    transformation_service: TransformationService,
) -> PromotionResult:
    return _promote_with_flow(
        run_id,
        service=account_service,
        transformation_service=transformation_service,
        flow=_ACCOUNT_TRANSACTION_FLOW,
    )


def promote_subscription_run(
    run_id: str,
    *,
    subscription_service: SubscriptionService,
    transformation_service: TransformationService,
) -> PromotionResult:
    return _promote_with_flow(
        run_id,
        service=subscription_service,
        transformation_service=transformation_service,
        flow=_SUBSCRIPTION_FLOW,
    )


def promote_contract_price_run(
    run_id: str,
    *,
    contract_price_service: ContractPriceService,
    transformation_service: TransformationService,
) -> PromotionResult:
    return _promote_with_flow(
        run_id,
        service=contract_price_service,
        transformation_service=transformation_service,
        flow=_CONTRACT_PRICE_FLOW,
    )


def promote_utility_usage_run(
    run_id: str,
    *,
    utility_usage_service: UtilityUsageService,
    transformation_service: TransformationService,
) -> PromotionResult:
    return _promote_with_flow(
        run_id,
        service=utility_usage_service,
        transformation_service=transformation_service,
        flow=_UTILITY_USAGE_FLOW,
    )


def promote_utility_bill_run(
    run_id: str,
    *,
    utility_bill_service: UtilityBillService,
    transformation_service: TransformationService,
) -> PromotionResult:
    return _promote_with_flow(
        run_id,
        service=utility_bill_service,
        transformation_service=transformation_service,
        flow=_UTILITY_BILL_FLOW,
    )


def _build_runtime_runner(
    flow: BuiltinPromotionFlowSpec,
) -> Callable[[PromotionRuntime], PromotionResult]:
    def run(runtime: PromotionRuntime) -> PromotionResult:
        return _promote_with_flow(
            runtime.run_id,
            service=flow.build_runtime_service(runtime),
            transformation_service=runtime.transformation_service,  # type: ignore[arg-type]
            flow=flow,
        )

    return run


_BUILTIN_PROMOTION_HANDLERS = {
    flow.package_spec.handler_key: BuiltinPromotionHandler(
        package_spec=get_builtin_transformation_package_spec_by_handler_key(
            flow.package_spec.handler_key
        ),
        runner=_build_runtime_runner(flow),
    )
    for flow in _BUILTIN_PROMOTION_FLOWS
}


def get_builtin_promotion_handler(handler_key: str) -> BuiltinPromotionHandler:
    try:
        return _BUILTIN_PROMOTION_HANDLERS[handler_key]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported built-in transformation package handler: {handler_key}"
        ) from exc
