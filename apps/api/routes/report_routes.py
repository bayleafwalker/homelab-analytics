from __future__ import annotations

from datetime import date
from typing import Any, Callable

from fastapi import FastAPI, HTTPException

from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.reporting_service import ReportingService
from packages.pipelines.transformation_service import TransformationService
from packages.shared.extensions import ExtensionRegistry


def register_report_routes(
    app: FastAPI,
    *,
    service: AccountTransactionService,
    registry: ExtensionRegistry,
    transformation_service: TransformationService | None,
    resolved_reporting_service: ReportingService | None,
    to_jsonable: Callable[[Any], Any],
) -> None:
    @app.get("/reports/monthly-cashflow")
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

    @app.get("/reports/utility-cost-summary")
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

    @app.get("/reports/current-dimensions/{dimension_name}")
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

    @app.get("/reports/monthly-cashflow-by-counterparty")
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

    @app.get("/reports/subscription-summary")
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

    @app.get("/reports/contract-prices")
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

    @app.get("/reports/electricity-prices")
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

    @app.get("/transformation-audit")
    async def get_transformation_audit(run_id: str | None = None) -> dict[str, Any]:
        if resolved_reporting_service is None:
            raise HTTPException(
                status_code=404,
                detail="Transformation audit requires a transformation service.",
            )
        records = resolved_reporting_service.get_transformation_audit(
            input_run_id=run_id
        )
        return {"audit": to_jsonable(records)}

    @app.get("/reports/{extension_key}")
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
