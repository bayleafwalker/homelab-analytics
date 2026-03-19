from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BuiltinPublicationSpec:
    publication_definition_id: str
    publication_key: str
    name: str


@dataclass(frozen=True)
class BuiltinTransformationPackageSpec:
    transformation_package_id: str
    handler_key: str
    name: str
    description: str
    version: int
    publications: tuple[BuiltinPublicationSpec, ...]
    refresh_publication_keys: tuple[str, ...] = ()

    @property
    def publication_keys(self) -> tuple[str, ...]:
        return tuple(publication.publication_key for publication in self.publications)


BUILTIN_TRANSFORMATION_PACKAGE_SPECS = (
    BuiltinTransformationPackageSpec(
        transformation_package_id="builtin_account_transactions",
        handler_key="account_transactions",
        name="Built-in account transactions",
        description="Canonical account transaction transformation and reporting flow.",
        version=1,
        publications=(
            BuiltinPublicationSpec(
                publication_definition_id="pub_account_transactions_monthly_cashflow",
                publication_key="mart_monthly_cashflow",
                name="Monthly cashflow mart",
            ),
            BuiltinPublicationSpec(
                publication_definition_id=(
                    "pub_account_transactions_counterparty_cashflow"
                ),
                publication_key="mart_monthly_cashflow_by_counterparty",
                name="Monthly cashflow by counterparty mart",
            ),
            BuiltinPublicationSpec(
                publication_definition_id="pub_account_transactions_current_accounts",
                publication_key="rpt_current_dim_account",
                name="Current account view",
            ),
            BuiltinPublicationSpec(
                publication_definition_id=(
                    "pub_account_transactions_current_counterparties"
                ),
                publication_key="rpt_current_dim_counterparty",
                name="Current counterparty view",
            ),
            BuiltinPublicationSpec(
                publication_definition_id=(
                    "pub_account_transactions_spend_by_category"
                ),
                publication_key="mart_spend_by_category_monthly",
                name="Spend by category monthly mart",
            ),
            BuiltinPublicationSpec(
                publication_definition_id=(
                    "pub_account_transactions_recent_large"
                ),
                publication_key="mart_recent_large_transactions",
                name="Recent large transactions mart",
            ),
            BuiltinPublicationSpec(
                publication_definition_id=(
                    "pub_account_transactions_balance_trend"
                ),
                publication_key="mart_account_balance_trend",
                name="Account balance trend mart",
            ),
            BuiltinPublicationSpec(
                publication_definition_id=(
                    "pub_account_transactions_anomalies_current"
                ),
                publication_key="mart_transaction_anomalies_current",
                name="Transaction anomalies current mart",
            ),
        ),
        refresh_publication_keys=(
            "mart_monthly_cashflow",
            "mart_monthly_cashflow_by_counterparty",
            "mart_spend_by_category_monthly",
            "mart_recent_large_transactions",
            "mart_account_balance_trend",
            "mart_transaction_anomalies_current",
        ),
    ),
    BuiltinTransformationPackageSpec(
        transformation_package_id="builtin_subscriptions",
        handler_key="subscriptions",
        name="Built-in subscriptions",
        description="Recurring subscription transformation and summary publications.",
        version=1,
        publications=(
            BuiltinPublicationSpec(
                publication_definition_id="pub_subscriptions_summary",
                publication_key="mart_subscription_summary",
                name="Subscription summary mart",
            ),
            BuiltinPublicationSpec(
                publication_definition_id="pub_subscriptions_upcoming_fixed_costs",
                publication_key="mart_upcoming_fixed_costs_30d",
                name="Upcoming fixed costs (30-day) mart",
            ),
            BuiltinPublicationSpec(
                publication_definition_id="pub_subscriptions_current_contracts",
                publication_key="rpt_current_dim_contract",
                name="Current contract view",
            ),
        ),
        refresh_publication_keys=(
            "mart_subscription_summary",
            "mart_upcoming_fixed_costs_30d",
        ),
    ),
    BuiltinTransformationPackageSpec(
        transformation_package_id="builtin_contract_prices",
        handler_key="contract_prices",
        name="Built-in contract prices",
        description="Contract pricing and electricity tariff transformation and publications.",
        version=1,
        publications=(
            BuiltinPublicationSpec(
                publication_definition_id="pub_contract_prices_current",
                publication_key="mart_contract_price_current",
                name="Current contract price mart",
            ),
            BuiltinPublicationSpec(
                publication_definition_id=(
                    "pub_contract_prices_electricity_current"
                ),
                publication_key="mart_electricity_price_current",
                name="Current electricity price mart",
            ),
            BuiltinPublicationSpec(
                publication_definition_id="pub_contract_prices_current_contracts",
                publication_key="rpt_current_dim_contract",
                name="Current contract view",
            ),
            BuiltinPublicationSpec(
                publication_definition_id="pub_contract_prices_review_candidates",
                publication_key="mart_contract_review_candidates",
                name="Contract review candidates mart",
            ),
            BuiltinPublicationSpec(
                publication_definition_id="pub_contract_prices_renewal_watchlist",
                publication_key="mart_contract_renewal_watchlist",
                name="Contract renewal watchlist mart",
            ),
        ),
        refresh_publication_keys=(
            "mart_contract_price_current",
            "mart_electricity_price_current",
            "mart_contract_review_candidates",
            "mart_contract_renewal_watchlist",
        ),
    ),
    BuiltinTransformationPackageSpec(
        transformation_package_id="builtin_utility_usage",
        handler_key="utility_usage",
        name="Built-in utility usage",
        description="Utility usage transformation and reporting publications.",
        version=1,
        publications=(
            BuiltinPublicationSpec(
                publication_definition_id="pub_utility_usage_summary",
                publication_key="mart_utility_cost_summary",
                name="Utility cost summary mart",
            ),
            BuiltinPublicationSpec(
                publication_definition_id="pub_utility_usage_cost_trend",
                publication_key="mart_utility_cost_trend_monthly",
                name="Utility cost trend monthly mart",
            ),
            BuiltinPublicationSpec(
                publication_definition_id="pub_utility_usage_vs_price",
                publication_key="mart_usage_vs_price_summary",
                name="Usage vs price summary mart",
            ),
            BuiltinPublicationSpec(
                publication_definition_id="pub_utility_usage_current_meters",
                publication_key="rpt_current_dim_meter",
                name="Current meter view",
            ),
        ),
        refresh_publication_keys=(
            "mart_utility_cost_summary",
            "mart_utility_cost_trend_monthly",
            "mart_usage_vs_price_summary",
        ),
    ),
    BuiltinTransformationPackageSpec(
        transformation_package_id="builtin_utility_bills",
        handler_key="utility_bills",
        name="Built-in utility bills",
        description="Utility bill transformation and reporting publications.",
        version=1,
        publications=(
            BuiltinPublicationSpec(
                publication_definition_id="pub_utility_bills_summary",
                publication_key="mart_utility_cost_summary",
                name="Utility cost summary mart",
            ),
            BuiltinPublicationSpec(
                publication_definition_id="pub_utility_bills_cost_trend",
                publication_key="mart_utility_cost_trend_monthly",
                name="Utility cost trend monthly mart",
            ),
            BuiltinPublicationSpec(
                publication_definition_id="pub_utility_bills_vs_price",
                publication_key="mart_usage_vs_price_summary",
                name="Usage vs price summary mart",
            ),
            BuiltinPublicationSpec(
                publication_definition_id="pub_utility_bills_current_meters",
                publication_key="rpt_current_dim_meter",
                name="Current meter view",
            ),
        ),
        refresh_publication_keys=(
            "mart_utility_cost_summary",
            "mart_utility_cost_trend_monthly",
            "mart_usage_vs_price_summary",
        ),
    ),
)

BUILTIN_TRANSFORMATION_PACKAGE_SPECS_BY_ID = {
    spec.transformation_package_id: spec
    for spec in BUILTIN_TRANSFORMATION_PACKAGE_SPECS
}
BUILTIN_TRANSFORMATION_PACKAGE_SPECS_BY_HANDLER_KEY = {
    spec.handler_key: spec for spec in BUILTIN_TRANSFORMATION_PACKAGE_SPECS
}


def get_builtin_transformation_package_spec(
    transformation_package_id: str,
) -> BuiltinTransformationPackageSpec:
    try:
        return BUILTIN_TRANSFORMATION_PACKAGE_SPECS_BY_ID[transformation_package_id]
    except KeyError as exc:
        raise KeyError(
            f"Unknown built-in transformation package: {transformation_package_id}"
        ) from exc


def get_builtin_transformation_package_spec_by_handler_key(
    handler_key: str,
) -> BuiltinTransformationPackageSpec:
    try:
        return BUILTIN_TRANSFORMATION_PACKAGE_SPECS_BY_HANDLER_KEY[handler_key]
    except KeyError as exc:
        raise KeyError(
            f"Unknown built-in transformation handler: {handler_key}"
        ) from exc
