from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.builtin_packages import (
    BuiltinTransformationPackageSpec,
    get_builtin_transformation_package_spec,
)
from packages.pipelines.contract_price_service import ContractPriceService
from packages.pipelines.promotion_registry import (
    CanonicalPromotionProcessor,
    PromotionHandler,
    PromotionHandlerRegistry,
    build_canonical_promotion_handler,
    run_canonical_promotion,
)
from packages.pipelines.promotion_types import PromotionResult
from packages.pipelines.subscription_service import SubscriptionService
from packages.pipelines.transformation_service import TransformationService
from packages.pipelines.utility_bill_service import UtilityBillService
from packages.pipelines.utility_usage_service import UtilityUsageService


@dataclass(frozen=True)
class BuiltinPromotionSpec:
    package_spec: BuiltinTransformationPackageSpec
    processor: CanonicalPromotionProcessor[Any, Any]

    @property
    def publication_keys(self) -> tuple[str, ...]:
        return self.package_spec.publication_keys

    @property
    def refresh_publication_keys(self) -> tuple[str, ...]:
        return self.package_spec.refresh_publication_keys


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


_ACCOUNT_TRANSACTION_SPEC = BuiltinPromotionSpec(
    package_spec=get_builtin_transformation_package_spec("builtin_account_transactions"),
    processor=CanonicalPromotionProcessor(
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
        count_existing=lambda transformation_service, run_id: (
            transformation_service.count_transactions(run_id)
        ),
        load_rows=_load_transaction_rows,
        required_header=_ACCOUNT_TRANSACTION_HEADER,
        contract_mismatch_reason="run does not match the account-transaction canonical contract",
    ),
)

_SUBSCRIPTION_SPEC = BuiltinPromotionSpec(
    package_spec=get_builtin_transformation_package_spec("builtin_subscriptions"),
    processor=CanonicalPromotionProcessor(
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
        count_existing=lambda transformation_service, run_id: (
            transformation_service.count_subscriptions(run_id)
        ),
        load_rows=_load_subscription_rows,
    ),
)

_CONTRACT_PRICE_SPEC = BuiltinPromotionSpec(
    package_spec=get_builtin_transformation_package_spec("builtin_contract_prices"),
    processor=CanonicalPromotionProcessor(
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
        count_existing=lambda transformation_service, run_id: (
            transformation_service.count_contract_prices(run_id)
        ),
        load_rows=_load_contract_price_rows,
        required_header=_CONTRACT_PRICE_HEADER,
        contract_mismatch_reason="run does not match the contract-price canonical contract",
    ),
)

_UTILITY_USAGE_SPEC = BuiltinPromotionSpec(
    package_spec=get_builtin_transformation_package_spec("builtin_utility_usage"),
    processor=CanonicalPromotionProcessor(
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
        count_existing=lambda transformation_service, run_id: (
            transformation_service.count_utility_usage(run_id)
        ),
        load_rows=_load_utility_usage_rows,
        required_header=_UTILITY_USAGE_HEADER,
        contract_mismatch_reason="run does not match the utility-usage canonical contract",
    ),
)

_UTILITY_BILL_SPEC = BuiltinPromotionSpec(
    package_spec=get_builtin_transformation_package_spec("builtin_utility_bills"),
    processor=CanonicalPromotionProcessor(
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
    ),
)

_BUILTIN_PROMOTION_SPECS = (
    _ACCOUNT_TRANSACTION_SPEC,
    _SUBSCRIPTION_SPEC,
    _CONTRACT_PRICE_SPEC,
    _UTILITY_USAGE_SPEC,
    _UTILITY_BILL_SPEC,
)


def _promote_with_spec(
    run_id: str,
    *,
    service: Any,
    transformation_service: TransformationService,
    spec: BuiltinPromotionSpec,
) -> PromotionResult:
    return run_canonical_promotion(
        run_id,
        service=service,
        transformation_service=transformation_service,
        processor=spec.processor,
        publication_keys=spec.publication_keys,
        refresh_publication_keys=spec.refresh_publication_keys,
    )


def promote_run(
    run_id: str,
    *,
    account_service: AccountTransactionService,
    transformation_service: TransformationService,
) -> PromotionResult:
    return _promote_with_spec(
        run_id,
        service=account_service,
        transformation_service=transformation_service,
        spec=_ACCOUNT_TRANSACTION_SPEC,
    )


def promote_subscription_run(
    run_id: str,
    *,
    subscription_service: SubscriptionService,
    transformation_service: TransformationService,
) -> PromotionResult:
    return _promote_with_spec(
        run_id,
        service=subscription_service,
        transformation_service=transformation_service,
        spec=_SUBSCRIPTION_SPEC,
    )


def promote_contract_price_run(
    run_id: str,
    *,
    contract_price_service: ContractPriceService,
    transformation_service: TransformationService,
) -> PromotionResult:
    return _promote_with_spec(
        run_id,
        service=contract_price_service,
        transformation_service=transformation_service,
        spec=_CONTRACT_PRICE_SPEC,
    )


def promote_utility_usage_run(
    run_id: str,
    *,
    utility_usage_service: UtilityUsageService,
    transformation_service: TransformationService,
) -> PromotionResult:
    return _promote_with_spec(
        run_id,
        service=utility_usage_service,
        transformation_service=transformation_service,
        spec=_UTILITY_USAGE_SPEC,
    )


def promote_utility_bill_run(
    run_id: str,
    *,
    utility_bill_service: UtilityBillService,
    transformation_service: TransformationService,
) -> PromotionResult:
    return _promote_with_spec(
        run_id,
        service=utility_bill_service,
        transformation_service=transformation_service,
        spec=_UTILITY_BILL_SPEC,
    )


_BUILTIN_PROMOTION_HANDLERS = {
    spec.package_spec.handler_key: build_canonical_promotion_handler(
        handler_key=spec.package_spec.handler_key,
        default_publications=spec.package_spec.publication_keys,
        refresh_publication_keys=spec.package_spec.refresh_publication_keys,
        processor=spec.processor,
    )
    for spec in _BUILTIN_PROMOTION_SPECS
}


def register_builtin_promotion_handlers(
    registry: PromotionHandlerRegistry,
) -> None:
    for handler in _BUILTIN_PROMOTION_HANDLERS.values():
        registry.register(handler)


def get_builtin_promotion_handler(handler_key: str) -> PromotionHandler:
    try:
        return _BUILTIN_PROMOTION_HANDLERS[handler_key]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported built-in transformation package handler: {handler_key}"
        ) from exc
