from __future__ import annotations

from packages.pipelines.builtin_packages import BUILTIN_TRANSFORMATION_PACKAGE_SPECS
from packages.pipelines.builtin_reporting import PUBLICATION_RELATIONS
from packages.pipelines.transformation_refresh_registry import (
    PublicationRefreshHandler,
    PublicationRefreshRegistry,
)

BUILTIN_PUBLICATION_REFRESH_HANDLERS: dict[str, PublicationRefreshHandler] = {
    "mart_monthly_cashflow": lambda service: service.refresh_monthly_cashflow(),
    "mart_monthly_cashflow_by_counterparty": (
        lambda service: service.refresh_monthly_cashflow_by_counterparty()
    ),
    "mart_spend_by_category_monthly": (
        lambda service: service.refresh_spend_by_category_monthly()
    ),
    "mart_recent_large_transactions": (
        lambda service: service.refresh_recent_large_transactions()
    ),
    "mart_subscription_summary": (lambda service: service.refresh_subscription_summary()),
    "mart_contract_price_current": (lambda service: service.refresh_contract_price_current()),
    "mart_electricity_price_current": (lambda service: service.refresh_contract_price_current()),
    "mart_utility_cost_summary": (lambda service: service.refresh_utility_cost_summary()),
}


def register_builtin_publication_refresh_handlers(
    registry: PublicationRefreshRegistry,
) -> None:
    for publication_key, handler in BUILTIN_PUBLICATION_REFRESH_HANDLERS.items():
        registry.register(publication_key, handler)


def validate_builtin_publication_refresh_handlers() -> None:
    declared_publications = set(PUBLICATION_RELATIONS)
    handled_publications = set(BUILTIN_PUBLICATION_REFRESH_HANDLERS)
    for spec in BUILTIN_TRANSFORMATION_PACKAGE_SPECS:
        refresh_keys = set(spec.refresh_publication_keys)
        if not refresh_keys <= declared_publications:
            unknown = sorted(refresh_keys - declared_publications)
            raise ValueError(
                "Built-in transformation package refresh publications are not declared in the reporting registry: "
                f"{spec.transformation_package_id}: {unknown}"
            )
        if not refresh_keys <= handled_publications:
            missing = sorted(refresh_keys - handled_publications)
            raise ValueError(
                "Built-in transformation package refresh publications are not handled by the transformation refresh registry: "
                f"{spec.transformation_package_id}: {missing}"
            )


validate_builtin_publication_refresh_handlers()
