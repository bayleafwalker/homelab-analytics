from __future__ import annotations

from decimal import Decimal

from packages.pipelines.reporting_service import ReportingService
from packages.pipelines.transformation_service import TransformationService
from packages.shared.extensions import ExtensionPublication, ExtensionRegistry, LayerExtension
from packages.storage.duckdb_store import DuckDBStore


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
