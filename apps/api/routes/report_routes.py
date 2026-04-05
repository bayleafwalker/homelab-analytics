from __future__ import annotations

from datetime import date
from typing import Any, Callable

from fastapi import FastAPI, HTTPException

from apps.api.response_models import (
    build_object_response_model,
    build_row_model,
    build_row_union_type,
    build_rows_response_model,
)
from packages.domains.finance.pipelines.account_transaction_service import AccountTransactionService
from packages.domains.finance.pipelines.category_rules import (
    CATEGORY_OVERRIDE_COLUMNS,
    CATEGORY_RULE_COLUMNS,
)
from packages.domains.finance.pipelines.transaction_models import TRANSFORMATION_AUDIT_COLUMNS
from packages.pipelines.household_reporting import (
    CURRENT_DIMENSION_RELATIONS,
    PUBLICATION_RELATIONS,
)
from packages.pipelines.reporting_service import ReportingService
from packages.pipelines.transformation_service import TransformationService
from packages.shared.extensions import ExtensionRegistry


def _pascal_case(value: str) -> str:
    return "".join(part.title() for part in value.replace("-", "_").split("_"))


def _row_model(model_name: str, relation_name: str):
    return build_row_model(model_name, PUBLICATION_RELATIONS[relation_name].columns)


MONTHLY_CASHFLOW_ROW_MODEL = _row_model("MonthlyCashflowRow", "mart_monthly_cashflow")
MONTHLY_CASHFLOW_BY_COUNTERPARTY_ROW_MODEL = _row_model(
    "MonthlyCashflowByCounterpartyRow",
    "mart_monthly_cashflow_by_counterparty",
)
UTILITY_COST_SUMMARY_ROW_MODEL = build_row_model(
    "UtilityCostSummaryRow",
    [
        ("period", "VARCHAR NOT NULL"),
        ("period_start", "DATE NOT NULL"),
        ("period_end", "DATE NOT NULL"),
        ("meter_id", "VARCHAR NOT NULL"),
        ("meter_name", "VARCHAR NOT NULL"),
        ("utility_type", "VARCHAR NOT NULL"),
        ("usage_quantity", "DECIMAL(18,4) NOT NULL"),
        ("usage_unit", "VARCHAR"),
        ("billed_amount", "DECIMAL(18,4) NOT NULL"),
        ("currency", "VARCHAR"),
        ("unit_cost", "DECIMAL(18,4)"),
        ("bill_count", "INTEGER NOT NULL"),
        ("usage_record_count", "INTEGER NOT NULL"),
        ("coverage_status", "VARCHAR NOT NULL"),
    ],
)
SPEND_BY_CATEGORY_MONTHLY_ROW_MODEL = _row_model(
    "SpendByCategoryMonthlyRow",
    "mart_spend_by_category_monthly",
)
RECENT_LARGE_TRANSACTIONS_ROW_MODEL = _row_model(
    "RecentLargeTransactionsRow",
    "mart_recent_large_transactions",
)
ACCOUNT_BALANCE_TREND_ROW_MODEL = _row_model(
    "AccountBalanceTrendRow",
    "mart_account_balance_trend",
)
TRANSACTION_ANOMALIES_ROW_MODEL = _row_model(
    "TransactionAnomaliesRow",
    "mart_transaction_anomalies_current",
)
UPCOMING_FIXED_COSTS_ROW_MODEL = _row_model(
    "UpcomingFixedCostsRow",
    "mart_upcoming_fixed_costs_30d",
)
UTILITY_COST_TREND_ROW_MODEL = _row_model(
    "UtilityCostTrendRow",
    "mart_utility_cost_trend_monthly",
)
USAGE_VS_PRICE_ROW_MODEL = _row_model(
    "UsageVsPriceRow",
    "mart_usage_vs_price_summary",
)
CONTRACT_REVIEW_CANDIDATES_ROW_MODEL = _row_model(
    "ContractReviewCandidatesRow",
    "mart_contract_review_candidates",
)
CONTRACT_RENEWAL_WATCHLIST_ROW_MODEL = _row_model(
    "ContractRenewalWatchlistRow",
    "mart_contract_renewal_watchlist",
)
BUDGET_VARIANCE_ROW_MODEL = _row_model("BudgetVarianceRow", "mart_budget_variance")
BUDGET_ENVELOPE_DRIFT_ROW_MODEL = _row_model(
    "BudgetEnvelopeDriftRow",
    "mart_budget_envelope_drift",
)
BUDGET_PROGRESS_ROW_MODEL = _row_model(
    "BudgetProgressCurrentRow",
    "mart_budget_progress_current",
)
LOAN_OVERVIEW_ROW_MODEL = _row_model("LoanOverviewRow", "mart_loan_overview")
LOAN_SCHEDULE_ROW_MODEL = _row_model("LoanScheduleProjectedRow", "mart_loan_schedule_projected")
LOAN_VARIANCE_ROW_MODEL = _row_model("LoanRepaymentVarianceRow", "mart_loan_repayment_variance")
HOUSEHOLD_COST_MODEL_ROW_MODEL = _row_model(
    "HouseholdCostModelRow",
    "mart_household_cost_model",
)
COST_TREND_ROW_MODEL = _row_model("CostTrend12MRow", "mart_cost_trend_12m")
HOUSEHOLD_OVERVIEW_ROW_MODEL = _row_model("HouseholdOverviewRow", "mart_household_overview")
HOMELAB_ROI_ROW_MODEL = _row_model("HomelabRoiRow", "mart_homelab_roi")
ATTENTION_ITEMS_ROW_MODEL = _row_model("AttentionItemRow", "mart_open_attention_items")
RECENT_CHANGES_ROW_MODEL = _row_model(
    "RecentSignificantChangeRow",
    "mart_recent_significant_changes",
)
OPERATING_BASELINE_ROW_MODEL = _row_model(
    "CurrentOperatingBaselineRow",
    "mart_current_operating_baseline",
)
AFFORDABILITY_RATIOS_ROW_MODEL = _row_model(
    "AffordabilityRatiosRow",
    "mart_affordability_ratios",
)
RECURRING_COST_BASELINE_ROW_MODEL = _row_model(
    "RecurringCostBaselineRow",
    "mart_recurring_cost_baseline",
)
CATEGORY_RULE_ROW_MODEL = build_row_model("CategoryRuleRow", CATEGORY_RULE_COLUMNS)
CATEGORY_OVERRIDE_ROW_MODEL = build_row_model("CategoryOverrideRow", CATEGORY_OVERRIDE_COLUMNS)
TRANSFORMATION_AUDIT_ROW_MODEL = build_row_model(
    "TransformationAuditRow",
    TRANSFORMATION_AUDIT_COLUMNS,
)

CURRENT_DIMENSION_ROW_MODELS = {
    dimension_name: build_row_model(
        f"{_pascal_case(dimension_name)}Row",
        PUBLICATION_RELATIONS[relation_name].columns,
    )
    for dimension_name, relation_name in CURRENT_DIMENSION_RELATIONS.items()
}
CURRENT_DIMENSION_ROW_UNION = build_row_union_type(
    tuple(CURRENT_DIMENSION_ROW_MODELS.values())
)

MONTHLY_CASHFLOW_RESPONSE_MODEL = build_rows_response_model(
    "MonthlyCashflowResponse",
    MONTHLY_CASHFLOW_ROW_MODEL,
    {"from_month": (str | None, None), "to_month": (str | None, None)},
)
UTILITY_COST_SUMMARY_RESPONSE_MODEL = build_rows_response_model(
    "UtilityCostSummaryResponse",
    UTILITY_COST_SUMMARY_ROW_MODEL,
    {
        "utility_type": (str | None, None),
        "meter_id": (str | None, None),
        "from_period": (str | None, None),
        "to_period": (str | None, None),
        "granularity": (str, "month"),
    },
)
CURRENT_DIMENSION_RESPONSE_MODEL = build_rows_response_model(
    "CurrentDimensionResponse",
    CURRENT_DIMENSION_ROW_UNION,
    {"dimension": (str, ...)},
)
MONTHLY_CASHFLOW_BY_COUNTERPARTY_RESPONSE_MODEL = build_rows_response_model(
    "MonthlyCashflowByCounterpartyResponse",
    MONTHLY_CASHFLOW_BY_COUNTERPARTY_ROW_MODEL,
    {
        "from_month": (str | None, None),
        "to_month": (str | None, None),
        "counterparty": (str | None, None),
    },
)
SUBSCRIPTION_SUMMARY_RESPONSE_MODEL = build_rows_response_model(
    "SubscriptionSummaryResponse",
    build_row_model("SubscriptionSummaryRow", PUBLICATION_RELATIONS["mart_subscription_summary"].columns),
    {"status": (str | None, None), "currency": (str | None, None)},
)
CONTRACT_PRICE_CURRENT_RESPONSE_MODEL = build_rows_response_model(
    "ContractPriceCurrentResponse",
    build_row_model(
        "ContractPriceCurrentRow",
        PUBLICATION_RELATIONS["mart_contract_price_current"].columns,
    ),
    {"contract_type": (str | None, None), "status": (str | None, None)},
)
ELECTRICITY_PRICE_CURRENT_RESPONSE_MODEL = build_rows_response_model(
    "ElectricityPriceCurrentResponse",
    build_row_model(
        "ElectricityPriceCurrentRow",
        PUBLICATION_RELATIONS["mart_electricity_price_current"].columns,
    ),
)
TRANSFORMATION_AUDIT_RESPONSE_MODEL = build_rows_response_model(
    "TransformationAuditResponse",
    TRANSFORMATION_AUDIT_ROW_MODEL,
)
SPEND_BY_CATEGORY_RESPONSE_MODEL = build_rows_response_model(
    "SpendByCategoryMonthlyResponse",
    SPEND_BY_CATEGORY_MONTHLY_ROW_MODEL,
)
RECENT_LARGE_TRANSACTIONS_RESPONSE_MODEL = build_rows_response_model(
    "RecentLargeTransactionsResponse",
    RECENT_LARGE_TRANSACTIONS_ROW_MODEL,
)
ACCOUNT_BALANCE_TREND_RESPONSE_MODEL = build_rows_response_model(
    "AccountBalanceTrendResponse",
    ACCOUNT_BALANCE_TREND_ROW_MODEL,
)
TRANSACTION_ANOMALIES_RESPONSE_MODEL = build_rows_response_model(
    "TransactionAnomaliesResponse",
    TRANSACTION_ANOMALIES_ROW_MODEL,
)
UPCOMING_FIXED_COSTS_RESPONSE_MODEL = build_rows_response_model(
    "UpcomingFixedCostsResponse",
    UPCOMING_FIXED_COSTS_ROW_MODEL,
)
UTILITY_COST_TREND_RESPONSE_MODEL = build_rows_response_model(
    "UtilityCostTrendResponse",
    UTILITY_COST_TREND_ROW_MODEL,
    {"utility_type": (str | None, None)},
)
USAGE_VS_PRICE_RESPONSE_MODEL = build_rows_response_model(
    "UsageVsPriceResponse",
    USAGE_VS_PRICE_ROW_MODEL,
    {"utility_type": (str | None, None)},
)
CONTRACT_REVIEW_CANDIDATES_RESPONSE_MODEL = build_rows_response_model(
    "ContractReviewCandidatesResponse",
    CONTRACT_REVIEW_CANDIDATES_ROW_MODEL,
)
CONTRACT_RENEWAL_WATCHLIST_RESPONSE_MODEL = build_rows_response_model(
    "ContractRenewalWatchlistResponse",
    CONTRACT_RENEWAL_WATCHLIST_ROW_MODEL,
)
BUDGET_VARIANCE_RESPONSE_MODEL = build_rows_response_model(
    "BudgetVarianceResponse",
    BUDGET_VARIANCE_ROW_MODEL,
)
BUDGET_ENVELOPE_DRIFT_RESPONSE_MODEL = build_rows_response_model(
    "BudgetEnvelopeDriftResponse",
    BUDGET_ENVELOPE_DRIFT_ROW_MODEL,
)
BUDGET_PROGRESS_RESPONSE_MODEL = build_rows_response_model(
    "BudgetProgressResponse",
    BUDGET_PROGRESS_ROW_MODEL,
)
LOAN_OVERVIEW_RESPONSE_MODEL = build_rows_response_model(
    "LoanOverviewResponse",
    LOAN_OVERVIEW_ROW_MODEL,
)
LOAN_SCHEDULE_RESPONSE_MODEL = build_rows_response_model(
    "LoanScheduleResponse",
    LOAN_SCHEDULE_ROW_MODEL,
    {"loan_id": (str, ...)},
)
LOAN_VARIANCE_RESPONSE_MODEL = build_rows_response_model(
    "LoanVarianceResponse",
    LOAN_VARIANCE_ROW_MODEL,
    {"loan_id": (str | None, None)},
)
HOUSEHOLD_COST_MODEL_RESPONSE_MODEL = build_rows_response_model(
    "HouseholdCostModelResponse",
    HOUSEHOLD_COST_MODEL_ROW_MODEL,
    {"period_label": (str | None, None), "cost_type": (str | None, None)},
)
COST_TREND_RESPONSE_MODEL = build_rows_response_model(
    "CostTrendResponse",
    COST_TREND_ROW_MODEL,
)
HOUSEHOLD_OVERVIEW_RESPONSE_MODEL = build_rows_response_model(
    "HouseholdOverviewResponse",
    HOUSEHOLD_OVERVIEW_ROW_MODEL,
)
HOMELAB_ROI_RESPONSE_MODEL = build_rows_response_model(
    "HomelabRoiResponse",
    HOMELAB_ROI_ROW_MODEL,
)
ATTENTION_ITEMS_RESPONSE_MODEL = build_rows_response_model(
    "AttentionItemsResponse",
    ATTENTION_ITEMS_ROW_MODEL,
)
RECENT_CHANGES_RESPONSE_MODEL = build_rows_response_model(
    "RecentChangesResponse",
    RECENT_CHANGES_ROW_MODEL,
)
OPERATING_BASELINE_RESPONSE_MODEL = build_rows_response_model(
    "OperatingBaselineResponse",
    OPERATING_BASELINE_ROW_MODEL,
)
AFFORDABILITY_RATIOS_RESPONSE_MODEL = build_rows_response_model(
    "AffordabilityRatiosResponse",
    AFFORDABILITY_RATIOS_ROW_MODEL,
)
RECURRING_COST_BASELINE_RESPONSE_MODEL = build_rows_response_model(
    "RecurringCostBaselineResponse",
    RECURRING_COST_BASELINE_ROW_MODEL,
)
CATEGORY_RULES_RESPONSE_MODEL = build_rows_response_model(
    "CategoryRulesResponse",
    CATEGORY_RULE_ROW_MODEL,
)
CATEGORY_OVERRIDES_RESPONSE_MODEL = build_rows_response_model(
    "CategoryOverridesResponse",
    CATEGORY_OVERRIDE_ROW_MODEL,
)
CATEGORY_RULE_CREATE_RESPONSE_MODEL = CATEGORY_RULE_ROW_MODEL
CATEGORY_OVERRIDE_CREATE_RESPONSE_MODEL = CATEGORY_OVERRIDE_ROW_MODEL
CATEGORY_DELETE_RESPONSE_MODEL = build_object_response_model(
    "CategoryDeleteResponse",
    {"status": (str, ...), "rule_id": (str, ...)},
)
CATEGORY_OVERRIDE_DELETE_RESPONSE_MODEL = build_object_response_model(
    "CategoryOverrideDeleteResponse",
    {"status": (str, ...), "counterparty_name": (str, ...)},
)
EXTENSION_REPORT_RESPONSE_MODEL = build_object_response_model(
    "ExtensionReportResponse",
    {"result": (Any, ...)},
)


def register_report_routes(
    app: FastAPI,
    *,
    service: AccountTransactionService,
    registry: ExtensionRegistry,
    transformation_service: TransformationService | None,
    resolved_reporting_service: ReportingService | None,
    to_jsonable: Callable[[Any], Any],
) -> None:
    @app.get("/reports/monthly-cashflow", response_model=MONTHLY_CASHFLOW_RESPONSE_MODEL)
    async def get_monthly_cashflow(
        from_month: str | None = None,
        to_month: str | None = None,
    ) -> dict[str, Any]:
        if resolved_reporting_service is None:
            raise HTTPException(
                status_code=404,
                detail="Monthly cashflow reporting requires a transformation service.",
            )
        rows = resolved_reporting_service.get_monthly_cashflow(
            from_month=from_month,
            to_month=to_month,
        )
        return {
            "rows": to_jsonable(rows),
            "from_month": from_month,
            "to_month": to_month,
        }

    @app.get("/reports/utility-cost-summary", response_model=UTILITY_COST_SUMMARY_RESPONSE_MODEL)
    async def get_utility_cost_summary(
        utility_type: str | None = None,
        meter_id: str | None = None,
        from_period: date | None = None,
        to_period: date | None = None,
        granularity: str = "month",
    ) -> dict[str, Any]:
        if resolved_reporting_service is None:
            raise HTTPException(
                status_code=404,
                detail="Utility cost reporting requires a transformation service.",
            )
        rows = resolved_reporting_service.get_utility_cost_summary(
            utility_type=utility_type,
            meter_id=meter_id,
            from_period=from_period,
            to_period=to_period,
            granularity=granularity,
        )
        return {
            "rows": to_jsonable(rows),
            "utility_type": utility_type,
            "meter_id": meter_id,
            "from_period": from_period.isoformat() if from_period else None,
            "to_period": to_period.isoformat() if to_period else None,
            "granularity": granularity,
        }

    @app.get(
        "/reports/current-dimensions/{dimension_name}",
        response_model=CURRENT_DIMENSION_RESPONSE_MODEL,
    )
    async def get_current_dimension_report(dimension_name: str) -> dict[str, Any]:
        if resolved_reporting_service is None:
            raise HTTPException(
                status_code=404,
                detail="Current-dimension reporting is not configured.",
            )
        return {
            "dimension": dimension_name,
            "rows": to_jsonable(
                resolved_reporting_service.get_current_dimension_rows(dimension_name)
            ),
        }

    @app.get(
        "/reports/monthly-cashflow-by-counterparty",
        response_model=MONTHLY_CASHFLOW_BY_COUNTERPARTY_RESPONSE_MODEL,
    )
    async def get_monthly_cashflow_by_counterparty(
        from_month: str | None = None,
        to_month: str | None = None,
        counterparty: str | None = None,
    ) -> dict[str, Any]:
        if resolved_reporting_service is None:
            raise HTTPException(
                status_code=404,
                detail="Counterparty cashflow reporting requires a transformation service.",
            )
        rows = resolved_reporting_service.get_monthly_cashflow_by_counterparty(
            from_month=from_month,
            to_month=to_month,
            counterparty_name=counterparty,
        )
        return {
            "rows": to_jsonable(rows),
            "from_month": from_month,
            "to_month": to_month,
            "counterparty": counterparty,
        }

    @app.get("/reports/subscription-summary", response_model=SUBSCRIPTION_SUMMARY_RESPONSE_MODEL)
    async def get_subscription_summary(
        status: str | None = None,
        currency: str | None = None,
    ) -> dict[str, Any]:
        if resolved_reporting_service is None:
            raise HTTPException(
                status_code=404,
                detail="Subscription reporting requires a transformation service.",
            )
        return {
            "rows": to_jsonable(
                resolved_reporting_service.get_subscription_summary(
                    status=status,
                    currency=currency,
                )
            ),
            "status": status,
            "currency": currency,
        }

    @app.get("/reports/contract-prices", response_model=CONTRACT_PRICE_CURRENT_RESPONSE_MODEL)
    async def get_contract_price_current(
        contract_type: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        if resolved_reporting_service is None:
            raise HTTPException(
                status_code=404,
                detail="Contract-price reporting requires a transformation service.",
            )
        return {
            "rows": to_jsonable(
                resolved_reporting_service.get_contract_price_current(
                    contract_type=contract_type,
                    status=status,
                )
            ),
            "contract_type": contract_type,
            "status": status,
        }

    @app.get(
        "/reports/electricity-prices",
        response_model=ELECTRICITY_PRICE_CURRENT_RESPONSE_MODEL,
    )
    async def get_electricity_price_current() -> dict[str, Any]:
        if resolved_reporting_service is None:
            raise HTTPException(
                status_code=404,
                detail="Electricity price reporting requires a transformation service.",
            )
        return {
            "rows": to_jsonable(
                resolved_reporting_service.get_electricity_price_current()
            )
        }

    @app.get("/transformation-audit", response_model=TRANSFORMATION_AUDIT_RESPONSE_MODEL)
    async def get_transformation_audit(run_id: str | None = None) -> dict[str, Any]:
        if resolved_reporting_service is None:
            raise HTTPException(
                status_code=404,
                detail="Transformation audit requires a transformation service.",
            )
        records = resolved_reporting_service.get_transformation_audit(
            input_run_id=run_id
        )
        return {"rows": to_jsonable(records)}

    # ------------------------------------------------------------------
    # Finance: new dedicated endpoints
    # ------------------------------------------------------------------

    @app.get(
        "/reports/spend-by-category-monthly",
        response_model=SPEND_BY_CATEGORY_RESPONSE_MODEL,
    )
    async def get_spend_by_category_monthly(
        from_month: str | None = None,
        to_month: str | None = None,
        counterparty: str | None = None,
        category: str | None = None,
    ) -> dict[str, Any]:
        if resolved_reporting_service is None:
            raise HTTPException(status_code=404, detail="Requires a transformation service.")
        rows = resolved_reporting_service.get_spend_by_category_monthly(
            from_month=from_month,
            to_month=to_month,
            counterparty_name=counterparty,
            category=category,
        )
        return {"rows": to_jsonable(rows)}

    @app.get(
        "/reports/recent-large-transactions",
        response_model=RECENT_LARGE_TRANSACTIONS_RESPONSE_MODEL,
    )
    async def get_recent_large_transactions() -> dict[str, Any]:
        if resolved_reporting_service is None:
            raise HTTPException(status_code=404, detail="Requires a transformation service.")
        return {"rows": to_jsonable(resolved_reporting_service.get_recent_large_transactions())}

    @app.get(
        "/reports/account-balance-trend",
        response_model=ACCOUNT_BALANCE_TREND_RESPONSE_MODEL,
    )
    async def get_account_balance_trend(
        account_id: str | None = None,
        from_month: str | None = None,
        to_month: str | None = None,
    ) -> dict[str, Any]:
        if resolved_reporting_service is None:
            raise HTTPException(status_code=404, detail="Requires a transformation service.")
        rows = resolved_reporting_service.get_account_balance_trend(
            account_id=account_id,
            from_month=from_month,
            to_month=to_month,
        )
        return {"rows": to_jsonable(rows)}

    @app.get(
        "/reports/transaction-anomalies",
        response_model=TRANSACTION_ANOMALIES_RESPONSE_MODEL,
    )
    async def get_transaction_anomalies() -> dict[str, Any]:
        if resolved_reporting_service is None:
            raise HTTPException(status_code=404, detail="Requires a transformation service.")
        return {"rows": to_jsonable(resolved_reporting_service.get_transaction_anomalies_current())}

    @app.get(
        "/reports/upcoming-fixed-costs",
        response_model=UPCOMING_FIXED_COSTS_RESPONSE_MODEL,
    )
    async def get_upcoming_fixed_costs() -> dict[str, Any]:
        if resolved_reporting_service is None:
            raise HTTPException(status_code=404, detail="Requires a transformation service.")
        return {"rows": to_jsonable(resolved_reporting_service.get_upcoming_fixed_costs_30d())}

    # ------------------------------------------------------------------
    # Utilities: new dedicated endpoints
    # ------------------------------------------------------------------

    @app.get(
        "/reports/utility-cost-trend",
        response_model=UTILITY_COST_TREND_RESPONSE_MODEL,
    )
    async def get_utility_cost_trend(
        utility_type: str | None = None,
    ) -> dict[str, Any]:
        if resolved_reporting_service is None:
            raise HTTPException(status_code=404, detail="Requires a transformation service.")
        rows = resolved_reporting_service.get_utility_cost_trend_monthly(
            utility_type=utility_type,
        )
        return {"rows": to_jsonable(rows)}

    @app.get("/reports/usage-vs-price", response_model=USAGE_VS_PRICE_RESPONSE_MODEL)
    async def get_usage_vs_price(
        utility_type: str | None = None,
    ) -> dict[str, Any]:
        if resolved_reporting_service is None:
            raise HTTPException(status_code=404, detail="Requires a transformation service.")
        rows = resolved_reporting_service.get_usage_vs_price_summary(
            utility_type=utility_type,
        )
        return {"rows": to_jsonable(rows)}

    @app.get(
        "/reports/contract-review-candidates",
        response_model=CONTRACT_REVIEW_CANDIDATES_RESPONSE_MODEL,
    )
    async def get_contract_review_candidates() -> dict[str, Any]:
        if resolved_reporting_service is None:
            raise HTTPException(status_code=404, detail="Requires a transformation service.")
        return {"rows": to_jsonable(resolved_reporting_service.get_contract_review_candidates())}

    @app.get(
        "/reports/contract-renewal-watchlist",
        response_model=CONTRACT_RENEWAL_WATCHLIST_RESPONSE_MODEL,
    )
    async def get_contract_renewal_watchlist() -> dict[str, Any]:
        if resolved_reporting_service is None:
            raise HTTPException(status_code=404, detail="Requires a transformation service.")
        return {"rows": to_jsonable(resolved_reporting_service.get_contract_renewal_watchlist())}

    # ------------------------------------------------------------------
    # Budget: dedicated endpoints
    # ------------------------------------------------------------------

    @app.get("/reports/budget-variance", response_model=BUDGET_VARIANCE_RESPONSE_MODEL)
    async def get_budget_variance(
        budget_name: str | None = None,
        category_id: str | None = None,
        period_label: str | None = None,
    ) -> dict[str, Any]:
        if transformation_service is None:
            raise HTTPException(status_code=404, detail="Requires a transformation service.")
        rows = transformation_service.get_budget_variance(
            budget_name=budget_name,
            category_id=category_id,
            period_label=period_label,
        )
        return {"rows": to_jsonable(rows)}

    @app.get("/reports/budget-envelopes", response_model=BUDGET_ENVELOPE_DRIFT_RESPONSE_MODEL)
    async def get_budget_envelopes(
        budget_name: str | None = None,
        category_id: str | None = None,
        period_label: str | None = None,
    ) -> dict[str, Any]:
        if transformation_service is None:
            raise HTTPException(status_code=404, detail="Requires a transformation service.")
        rows = transformation_service.get_budget_envelope_drift(
            budget_name=budget_name,
            category_id=category_id,
            period_label=period_label,
        )
        return {"rows": to_jsonable(rows)}

    @app.get("/reports/budget-progress", response_model=BUDGET_PROGRESS_RESPONSE_MODEL)
    async def get_budget_progress() -> dict[str, Any]:
        if transformation_service is None:
            raise HTTPException(status_code=404, detail="Requires a transformation service.")
        return {"rows": to_jsonable(transformation_service.get_budget_progress_current())}

    # ------------------------------------------------------------------
    # Loans: dedicated endpoints
    # ------------------------------------------------------------------

    @app.get("/reports/loan-overview", response_model=LOAN_OVERVIEW_RESPONSE_MODEL)
    async def get_loan_overview() -> dict[str, Any]:
        if transformation_service is None:
            raise HTTPException(status_code=404, detail="Requires a transformation service.")
        return {"rows": to_jsonable(transformation_service.get_loan_overview())}

    @app.get("/reports/loan-schedule/{loan_id}", response_model=LOAN_SCHEDULE_RESPONSE_MODEL)
    async def get_loan_schedule(loan_id: str) -> dict[str, Any]:
        if transformation_service is None:
            raise HTTPException(status_code=404, detail="Requires a transformation service.")
        rows = transformation_service.get_loan_schedule_projected(loan_id=loan_id)
        return {"loan_id": loan_id, "rows": to_jsonable(rows)}

    @app.get("/reports/loan-variance", response_model=LOAN_VARIANCE_RESPONSE_MODEL)
    async def get_loan_variance(loan_id: str | None = None) -> dict[str, Any]:
        if transformation_service is None:
            raise HTTPException(status_code=404, detail="Requires a transformation service.")
        rows = transformation_service.get_loan_repayment_variance(loan_id=loan_id)
        return {"rows": to_jsonable(rows)}

    # ------------------------------------------------------------------
    # Household cost model: dedicated endpoints
    # ------------------------------------------------------------------

    @app.get(
        "/reports/household-cost-model",
        response_model=HOUSEHOLD_COST_MODEL_RESPONSE_MODEL,
    )
    async def get_household_cost_model(
        period_label: str | None = None,
        cost_type: str | None = None,
    ) -> dict[str, Any]:
        if transformation_service is None:
            raise HTTPException(status_code=404, detail="Requires a transformation service.")
        rows = transformation_service.get_household_cost_model(
            period_label=period_label,
            cost_type=cost_type,
        )
        return {"rows": to_jsonable(rows)}

    @app.get("/reports/cost-trend", response_model=COST_TREND_RESPONSE_MODEL)
    async def get_cost_trend() -> dict[str, Any]:
        if transformation_service is None:
            raise HTTPException(status_code=404, detail="Requires a transformation service.")
        return {"rows": to_jsonable(transformation_service.get_cost_trend_12m())}

    # ------------------------------------------------------------------
    # Overview: new dedicated endpoints
    # ------------------------------------------------------------------

    @app.get("/reports/household-overview", response_model=HOUSEHOLD_OVERVIEW_RESPONSE_MODEL)
    async def get_household_overview() -> dict[str, Any]:
        if resolved_reporting_service is None:
            raise HTTPException(status_code=404, detail="Requires a transformation service.")
        return {"rows": to_jsonable(resolved_reporting_service.get_household_overview())}

    @app.get("/reports/homelab-roi", response_model=HOMELAB_ROI_RESPONSE_MODEL)
    async def get_homelab_roi() -> dict[str, Any]:
        if resolved_reporting_service is None:
            raise HTTPException(status_code=404, detail="Requires a transformation service.")
        return {"rows": to_jsonable(resolved_reporting_service.get_homelab_roi())}

    @app.get("/reports/attention-items", response_model=ATTENTION_ITEMS_RESPONSE_MODEL)
    async def get_attention_items() -> dict[str, Any]:
        if resolved_reporting_service is None:
            raise HTTPException(status_code=404, detail="Requires a transformation service.")
        return {"rows": to_jsonable(resolved_reporting_service.get_open_attention_items())}

    @app.get("/reports/recent-changes", response_model=RECENT_CHANGES_RESPONSE_MODEL)
    async def get_recent_changes() -> dict[str, Any]:
        if resolved_reporting_service is None:
            raise HTTPException(status_code=404, detail="Requires a transformation service.")
        return {"rows": to_jsonable(resolved_reporting_service.get_recent_significant_changes())}

    @app.get(
        "/reports/operating-baseline",
        response_model=OPERATING_BASELINE_RESPONSE_MODEL,
    )
    async def get_operating_baseline() -> dict[str, Any]:
        if resolved_reporting_service is None:
            raise HTTPException(status_code=404, detail="Requires a transformation service.")
        return {"rows": to_jsonable(resolved_reporting_service.get_current_operating_baseline())}

    @app.get(
        "/reports/affordability-ratios",
        response_model=AFFORDABILITY_RATIOS_RESPONSE_MODEL,
    )
    async def get_affordability_ratios() -> dict[str, Any]:
        if transformation_service is None:
            raise HTTPException(status_code=404, detail="Requires a transformation service.")
        return {"rows": to_jsonable(transformation_service.get_affordability_ratios())}

    @app.get(
        "/reports/recurring-cost-baseline",
        response_model=RECURRING_COST_BASELINE_RESPONSE_MODEL,
    )
    async def get_recurring_cost_baseline() -> dict[str, Any]:
        if transformation_service is None:
            raise HTTPException(status_code=404, detail="Requires a transformation service.")
        return {"rows": to_jsonable(transformation_service.get_recurring_cost_baseline())}

    # ------------------------------------------------------------------
    # Category rules and overrides
    # ------------------------------------------------------------------

    @app.get("/categories/rules", response_model=CATEGORY_RULES_RESPONSE_MODEL)
    async def get_category_rules() -> dict[str, Any]:
        if transformation_service is None:
            raise HTTPException(status_code=404, detail="Requires a transformation service.")
        rules = to_jsonable(transformation_service.list_category_rules())
        return {"rows": rules}

    @app.post("/categories/rules", status_code=201, response_model=CATEGORY_RULE_CREATE_RESPONSE_MODEL)
    async def create_category_rule(
        rule_id: str,
        pattern: str,
        category: str,
        priority: int = 0,
    ) -> dict[str, Any]:
        if transformation_service is None:
            raise HTTPException(status_code=404, detail="Requires a transformation service.")
        transformation_service.add_category_rule(
            rule_id=rule_id, pattern=pattern, category=category, priority=priority,
        )
        return {"rule_id": rule_id, "pattern": pattern, "category": category, "priority": priority}

    @app.delete("/categories/rules/{rule_id}", response_model=CATEGORY_DELETE_RESPONSE_MODEL)
    async def delete_category_rule(rule_id: str) -> dict[str, str]:
        if transformation_service is None:
            raise HTTPException(status_code=404, detail="Requires a transformation service.")
        transformation_service.remove_category_rule(rule_id=rule_id)
        return {"status": "deleted", "rule_id": rule_id}

    @app.get("/categories/overrides", response_model=CATEGORY_OVERRIDES_RESPONSE_MODEL)
    async def get_category_overrides() -> dict[str, Any]:
        if transformation_service is None:
            raise HTTPException(status_code=404, detail="Requires a transformation service.")
        overrides = to_jsonable(transformation_service.list_category_overrides())
        return {"rows": overrides}

    @app.put(
        "/categories/overrides/{counterparty_name}",
        response_model=CATEGORY_OVERRIDE_CREATE_RESPONSE_MODEL,
    )
    async def set_category_override_endpoint(
        counterparty_name: str,
        category: str,
    ) -> dict[str, str]:
        if transformation_service is None:
            raise HTTPException(status_code=404, detail="Requires a transformation service.")
        transformation_service.set_category_override(
            counterparty_name=counterparty_name, category=category,
        )
        return {"counterparty_name": counterparty_name, "category": category}

    @app.delete(
        "/categories/overrides/{counterparty_name}",
        response_model=CATEGORY_OVERRIDE_DELETE_RESPONSE_MODEL,
    )
    async def delete_category_override(counterparty_name: str) -> dict[str, str]:
        if transformation_service is None:
            raise HTTPException(status_code=404, detail="Requires a transformation service.")
        transformation_service.remove_category_override(counterparty_name=counterparty_name)
        return {"status": "deleted", "counterparty_name": counterparty_name}

    # ------------------------------------------------------------------
    # Extension-based reporting (catch-all, must be last)
    # ------------------------------------------------------------------

    @app.get("/reports/{extension_key}", response_model=EXTENSION_REPORT_RESPONSE_MODEL)
    async def run_reporting_extension(
        extension_key: str,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        if not run_id:
            raise HTTPException(status_code=400, detail="run_id is required")
        extension = registry.get_extension("reporting", extension_key)
        if extension.data_access == "published" and resolved_reporting_service is None:
            raise HTTPException(
                status_code=404,
                detail="Reporting extension requires a reporting service.",
            )
        if extension.data_access == "warehouse" and transformation_service is None:
            raise HTTPException(
                status_code=404,
                detail="Reporting extension requires a transformation service.",
            )
        result = registry.execute(
            "reporting",
            extension_key,
            service=service,
            reporting_service=resolved_reporting_service,
            transformation_service=transformation_service,
            run_id=run_id,
        )
        return {"result": to_jsonable(result)}
