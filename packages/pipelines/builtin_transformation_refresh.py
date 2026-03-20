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
    "mart_account_balance_trend": (
        lambda service: service.refresh_account_balance_trend()
    ),
    "mart_transaction_anomalies_current": (
        lambda service: service.refresh_transaction_anomalies_current()
    ),
    "mart_subscription_summary": (lambda service: service.refresh_subscription_summary()),
    "mart_upcoming_fixed_costs_30d": (
        lambda service: service.refresh_upcoming_fixed_costs_30d()
    ),
    "mart_contract_price_current": (lambda service: service.refresh_contract_price_current()),
    "mart_electricity_price_current": (lambda service: service.refresh_contract_price_current()),
    "mart_utility_cost_summary": (lambda service: service.refresh_utility_cost_summary()),
    "mart_utility_cost_trend_monthly": (
        lambda service: service.refresh_utility_cost_trend_monthly()
    ),
    "mart_usage_vs_price_summary": (
        lambda service: service.refresh_usage_vs_price_summary()
    ),
    "mart_contract_review_candidates": (
        lambda service: service.refresh_contract_review_candidates()
    ),
    "mart_contract_renewal_watchlist": (
        lambda service: service.refresh_contract_renewal_watchlist()
    ),
    "mart_budget_variance": (lambda service: service.refresh_budget_variance()),
    "mart_budget_progress_current": (
        lambda service: service.refresh_budget_progress_current()
    ),
    "mart_loan_schedule_projected": (
        lambda service: service.refresh_loan_schedule_projected()
    ),
    "mart_loan_repayment_variance": (
        lambda service: service.refresh_loan_repayment_variance()
    ),
    "mart_loan_overview": (lambda service: service.refresh_loan_overview()),
    "mart_household_overview": (lambda service: service.refresh_household_overview()),
    "mart_open_attention_items": (lambda service: service.refresh_open_attention_items()),
    "mart_recent_significant_changes": (
        lambda service: service.refresh_recent_significant_changes()
    ),
    "mart_current_operating_baseline": (
        lambda service: service.refresh_current_operating_baseline()
    ),
    "mart_household_cost_model": (
        lambda service: service.refresh_household_cost_model()
    ),
    "mart_cost_trend_12m": (
        lambda service: service.refresh_cost_trend_12m()
    ),
    "mart_affordability_ratios": (
        lambda service: service.refresh_affordability_ratios()
    ),
    "mart_recurring_cost_baseline": (
        lambda service: service.refresh_recurring_cost_baseline()
    ),
    "mart_service_health_current": (
        lambda service: service.refresh_service_health_current()
    ),
    "mart_backup_freshness": (lambda service: service.refresh_backup_freshness()),
    "mart_storage_risk": (lambda service: service.refresh_storage_risk()),
    "mart_workload_cost_7d": (lambda service: service.refresh_workload_cost_7d()),
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
