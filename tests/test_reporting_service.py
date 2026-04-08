from __future__ import annotations

from datetime import date
from decimal import Decimal

from packages.pipelines.reporting_service import ReportingService
from packages.pipelines.transformation_service import TransformationService
from packages.shared.extensions import ExtensionPublication, ExtensionRegistry, LayerExtension
from packages.storage.duckdb_store import DuckDBStore


def _seed_metric_reporting(ts: TransformationService) -> None:
    today = date.today()
    month_start = today.replace(day=1)

    ts.load_transactions(
        [
            {
                "booked_at": f"{today.year}-{today.month:02d}-03T08:00:00+00:00",
                "account_id": "checking",
                "counterparty_name": "Employer",
                "amount": "2500.00",
                "currency": "EUR",
                "description": "salary",
            },
            {
                "booked_at": f"{today.year}-{today.month:02d}-05T08:00:00+00:00",
                "account_id": "checking",
                "counterparty_name": "Landlord",
                "amount": "-900.00",
                "currency": "EUR",
                "description": "rent",
            },
        ],
        run_id="txn-001",
    )
    ts.refresh_monthly_cashflow()
    ts.refresh_household_overview()

    ts.load_utility_usage(
        [
            {
                "meter_id": "elec-001",
                "meter_name": "Main Meter",
                "utility_type": "electricity",
                "location": "home",
                "usage_start": month_start.isoformat(),
                "usage_end": today.isoformat(),
                "usage_quantity": "320.50",
                "usage_unit": "kWh",
                "reading_source": "smart-meter",
            }
        ],
        run_id="usage-001",
    )
    ts.load_bills(
        [
            {
                "meter_id": "elec-001",
                "meter_name": "Main Meter",
                "provider": "City Power",
                "utility_type": "electricity",
                "location": "home",
                "billing_period_start": month_start.isoformat(),
                "billing_period_end": today.isoformat(),
                "billed_amount": "48.08",
                "currency": "EUR",
                "billed_quantity": "320.50",
                "usage_unit": "kWh",
                "invoice_date": today.isoformat(),
            }
        ],
        run_id="bill-001",
    )
    ts.refresh_utility_cost_summary()
    ts.refresh_utility_cost_trend_monthly()
    ts.refresh_household_overview()

    ts.load_loan_repayments(
        [
            {
                "loan_id": "loan-001",
                "loan_name": "Test Mortgage",
                "lender": "Test Bank",
                "loan_type": "mortgage",
                "principal": "200000.00",
                "annual_rate": "0.045",
                "term_months": "240",
                "start_date": month_start.isoformat(),
                "payment_frequency": "monthly",
                "repayment_date": today.isoformat(),
                "repayment_month": f"{today.year}-{today.month:02d}",
                "payment_amount": "1265.00",
                "principal_portion": "515.00",
                "interest_portion": "750.00",
                "extra_amount": None,
                "currency": "EUR",
            }
        ],
        run_id="loan-001",
    )
    ts.refresh_loan_schedule_projected()


def test_reporting_service_falls_back_to_transformation_service_for_marts() -> None:
    transformation_service = TransformationService(DuckDBStore.memory())
    transformation_service.load_transactions(
        [
            {
                "booked_at": "2026-01-03T08:00:00+00:00",
                "account_id": "checking",
                "counterparty_name": "Employer",
                "amount": "2500.00",
                "currency": "EUR",
                "description": "salary",
            },
            {
                "booked_at": "2026-01-05T08:00:00+00:00",
                "account_id": "checking",
                "counterparty_name": "Landlord",
                "amount": "-900.00",
                "currency": "EUR",
                "description": "rent",
            },
        ],
        run_id="run-001",
    )
    transformation_service.refresh_monthly_cashflow()

    reporting_service = ReportingService(transformation_service)

    assert reporting_service.get_monthly_cashflow() == transformation_service.get_monthly_cashflow()


def test_reporting_service_metric_snapshots_use_reporting_layer_marts() -> None:
    transformation_service = TransformationService(DuckDBStore.memory())
    _seed_metric_reporting(transformation_service)

    reporting_service = ReportingService(transformation_service)

    cashflow = reporting_service.get_current_month_net_cashflow()
    assert cashflow.value == Decimal("1600.0000")
    assert cashflow.unit == "EUR"

    electricity = reporting_service.get_current_month_electricity_cost()
    assert electricity.value == Decimal("48.0800")
    assert electricity.unit == "EUR"

    next_payment = reporting_service.get_next_loan_payment_amount()
    assert next_payment.value == Decimal("1265.3000")
    assert next_payment.unit == "EUR"


def test_reporting_service_falls_back_to_transformation_service_for_current_dimensions() -> None:
    transformation_service = TransformationService(DuckDBStore.memory())
    transformation_service.load_transactions(
        [
            {
                "booked_at": "2026-01-03T08:00:00+00:00",
                "account_id": "checking",
                "counterparty_name": "Employer",
                "amount": "2500.00",
                "currency": "EUR",
                "description": "salary",
            }
        ],
        run_id="run-001",
    )

    reporting_service = ReportingService(transformation_service)

    assert reporting_service.get_current_dimension_rows(
        "dim_account"
    ) == transformation_service.get_current_dimension_rows("dim_account")


def test_reporting_service_falls_back_to_transformation_service_for_home_automation_entities() -> None:
    transformation_service = TransformationService(DuckDBStore.memory())
    transformation_service.load_home_automation_state(
        [
            {
                "entity_id": "sensor.living_room_temperature",
                "state": "21.3",
                "attributes": {
                    "friendly_name": "Living Room Temperature",
                    "unit_of_measurement": "°C",
                    "area_id": "living-room",
                    "integration": "home_assistant",
                },
                "last_changed": "2026-03-28T10:00:00+00:00",
            }
        ],
        run_id="run-001",
        source_system="home_assistant",
    )

    reporting_service = ReportingService(transformation_service)

    assert reporting_service.get_current_dimension_rows(
        "dim_entity"
    ) == transformation_service.get_current_dimension_rows("dim_entity")


def test_reporting_service_falls_back_to_transformation_service_for_assets() -> None:
    transformation_service = TransformationService(DuckDBStore.memory())
    transformation_service.load_domain_rows(
        "asset_register",
        [
            {
                "asset_name": "UPS Rack A",
                "asset_type": "ups",
                "purchase_date": "2024-01-15",
                "purchase_price": "1200.00",
                "currency": "EUR",
                "location": "rack-a",
            }
        ],
        run_id="run-001",
        source_system="manual-upload",
    )

    reporting_service = ReportingService(transformation_service)

    assert reporting_service.get_current_dimension_rows(
        "dim_asset"
    ) == transformation_service.get_current_dimension_rows("dim_asset")


def test_reporting_service_falls_back_to_transformation_service_for_audit() -> None:
    transformation_service = TransformationService(DuckDBStore.memory())
    transformation_service.load_transactions(
        [
            {
                "booked_at": "2026-01-03T08:00:00+00:00",
                "account_id": "checking",
                "counterparty_name": "Employer",
                "amount": "2500.00",
                "currency": "EUR",
                "description": "salary",
            }
        ],
        run_id="run-001",
    )

    reporting_service = ReportingService(transformation_service)

    assert reporting_service.get_transformation_audit() == (
        transformation_service.get_transformation_audit()
    )


def test_reporting_service_supports_extension_publication_relations() -> None:
    transformation_service = TransformationService(DuckDBStore.memory())
    transformation_service.load_transactions(
        [
            {
                "booked_at": "2026-01-03T08:00:00+00:00",
                "account_id": "checking",
                "counterparty_name": "Employer",
                "amount": "2500.00",
                "currency": "EUR",
                "description": "salary",
            },
            {
                "booked_at": "2026-01-05T08:00:00+00:00",
                "account_id": "checking",
                "counterparty_name": "Landlord",
                "amount": "-900.00",
                "currency": "EUR",
                "description": "rent",
            },
        ],
        run_id="run-001",
    )
    transformation_service.refresh_monthly_cashflow()
    registry = ExtensionRegistry()
    registry.register(
        LayerExtension(
            layer="reporting",
            key="external_budget_projection",
            kind="mart",
            description="External published budget projection.",
            module="tests.external_budget_projection",
            source="tests",
            data_access="published",
            publication_relations=(
                ExtensionPublication(
                    relation_name="mart_budget_projection",
                    columns=(
                        ("booking_month", "VARCHAR NOT NULL"),
                        ("net", "DECIMAL(18,4) NOT NULL"),
                    ),
                    source_query="SELECT booking_month, net FROM mart_monthly_cashflow",
                    order_by="booking_month",
                ),
            ),
            handler=lambda *, reporting_service: reporting_service.get_relation_rows(
                "mart_budget_projection"
            ),
        )
    )

    reporting_service = ReportingService(
        transformation_service,
        extension_registry=registry,
    )

    assert reporting_service.get_relation_rows("mart_budget_projection") == [
        {
            "booking_month": "2026-01",
            "net": Decimal("1600.0000"),
        }
    ]
    assert registry.execute(
        "reporting",
        "external_budget_projection",
        reporting_service=reporting_service,
    ) == [
        {
            "booking_month": "2026-01",
            "net": Decimal("1600.0000"),
        }
    ]
