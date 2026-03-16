from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.csv_validation import ColumnType
from packages.pipelines.reporting_service import ReportingService
from packages.pipelines.transformation_service import TransformationService
from packages.shared.extensions import ExtensionPublication, ExtensionRegistry, LayerExtension
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.ingestion_config import (
    ColumnMappingCreate,
    ColumnMappingRule,
    DatasetColumnConfig,
    DatasetContractConfigCreate,
    IngestionConfigRepository,
    PublicationDefinitionCreate,
    SourceAssetCreate,
    SourceSystemCreate,
)
from packages.storage.postgres_reporting import PostgresReportingStore
from packages.storage.run_metadata import RunMetadataRepository
from tests.postgres_test_support import running_postgres_container

pytestmark = [pytest.mark.integration, pytest.mark.slow]
ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


class _FailingTransformationService:
    def get_monthly_cashflow(self, *args, **kwargs):
        raise AssertionError("published reporting path should not read from DuckDB")

    def get_current_dimension_rows(self, *args, **kwargs):
        raise AssertionError("published reporting path should not read from DuckDB")

    def get_transformation_audit(self, *args, **kwargs):
        raise AssertionError("published audit path should not read from DuckDB")


def test_reporting_service_reads_published_marts_and_dimensions_from_postgres() -> None:
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

    with running_postgres_container() as dsn:
        publisher = ReportingService(
            transformation_service,
            publication_store=PostgresReportingStore(dsn),
        )
        published = publisher.publish_publications(
            ["mart_monthly_cashflow", "rpt_current_dim_account"]
        )

        reporting_service = ReportingService(
            _FailingTransformationService(),  # type: ignore[arg-type]
            publication_store=PostgresReportingStore(dsn),
        )
        monthly_rows = reporting_service.get_monthly_cashflow()
        account_rows = reporting_service.get_current_dimension_rows("dim_account")

    assert published == ["mart_monthly_cashflow", "rpt_current_dim_account"]
    assert monthly_rows == [
        {
            "booking_month": "2026-01",
            "income": Decimal("2500.0000"),
            "expense": Decimal("900.0000"),
            "net": Decimal("1600.0000"),
            "transaction_count": 2,
        }
    ]
    assert len(account_rows) == 1
    assert account_rows[0]["account_id"] == "checking"
    assert account_rows[0]["currency"] == "EUR"


def test_reporting_service_returns_same_results_in_warehouse_and_published_modes() -> None:
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

    warehouse_reporting_service = ReportingService(transformation_service)
    warehouse_monthly_rows = warehouse_reporting_service.get_monthly_cashflow()
    warehouse_account_rows = warehouse_reporting_service.get_current_dimension_rows(
        "dim_account"
    )

    with running_postgres_container() as dsn:
        publisher = ReportingService(
            transformation_service,
            publication_store=PostgresReportingStore(dsn),
        )
        publisher.publish_publications(
            ["mart_monthly_cashflow", "rpt_current_dim_account"]
        )

        published_reporting_service = ReportingService(
            _FailingTransformationService(),  # type: ignore[arg-type]
            publication_store=PostgresReportingStore(dsn),
        )
        published_monthly_rows = published_reporting_service.get_monthly_cashflow()
        published_account_rows = published_reporting_service.get_current_dimension_rows(
            "dim_account"
        )

    assert published_monthly_rows == warehouse_monthly_rows
    assert published_account_rows == warehouse_account_rows


def test_reporting_service_reads_published_transformation_audit_from_postgres() -> None:
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

    with running_postgres_container() as dsn:
        publisher = ReportingService(
            transformation_service,
            publication_store=PostgresReportingStore(dsn),
        )
        published = publisher.publish_auxiliary_relations(["transformation_audit"])

        reporting_service = ReportingService(
            _FailingTransformationService(),  # type: ignore[arg-type]
            publication_store=PostgresReportingStore(dsn),
        )
        audit_rows = reporting_service.get_transformation_audit()

    assert published == ["transformation_audit"]
    assert len(audit_rows) == 1
    assert audit_rows[0]["input_run_id"] == "run-001"
    assert audit_rows[0]["fact_rows"] == 1


def test_reporting_service_reads_extension_publication_relations_from_postgres() -> None:
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

    with running_postgres_container() as dsn:
        publisher = ReportingService(
            transformation_service,
            publication_store=PostgresReportingStore(dsn),
            extension_registry=registry,
        )
        published = publisher.publish_publications(["mart_budget_projection"])

        reporting_service = ReportingService(
            _FailingTransformationService(),  # type: ignore[arg-type]
            publication_store=PostgresReportingStore(dsn),
            extension_registry=registry,
        )
        rows = reporting_service.get_relation_rows("mart_budget_projection")

    assert published == ["mart_budget_projection"]
    assert rows == [
        {
            "booking_month": "2026-01",
            "net": Decimal("1600.0000"),
        }
    ]


def test_configured_source_asset_publications_can_include_extension_relations() -> None:
    with TemporaryDirectory() as temp_dir, running_postgres_container() as dsn:
        temp_root = Path(temp_dir)
        config_repository = IngestionConfigRepository(temp_root / "config.db")
        metadata_repository = RunMetadataRepository(temp_root / "runs.db")
        config_repository.create_source_system(
            SourceSystemCreate(
                source_system_id="bank_partner_export",
                name="Bank Partner Export",
                source_type="file-drop",
                transport="filesystem",
                schedule_mode="manual",
            )
        )
        config_repository.create_dataset_contract(
            DatasetContractConfigCreate(
                dataset_contract_id="household_account_transactions_v1",
                dataset_name="household_account_transactions",
                version=1,
                allow_extra_columns=False,
                columns=(
                    DatasetColumnConfig("booked_at", ColumnType.DATE),
                    DatasetColumnConfig("account_id", ColumnType.STRING),
                    DatasetColumnConfig("counterparty_name", ColumnType.STRING),
                    DatasetColumnConfig("amount", ColumnType.DECIMAL),
                    DatasetColumnConfig("currency", ColumnType.STRING),
                    DatasetColumnConfig("description", ColumnType.STRING, required=False),
                ),
            )
        )
        config_repository.create_column_mapping(
            ColumnMappingCreate(
                column_mapping_id="bank_partner_export_v1",
                source_system_id="bank_partner_export",
                dataset_contract_id="household_account_transactions_v1",
                version=1,
                rules=(
                    ColumnMappingRule("booked_at", source_column="booking_date"),
                    ColumnMappingRule("account_id", source_column="account_number"),
                    ColumnMappingRule("counterparty_name", source_column="payee"),
                    ColumnMappingRule("amount", source_column="amount_eur"),
                    ColumnMappingRule("currency", default_value="EUR"),
                    ColumnMappingRule("description", source_column="memo"),
                ),
            )
        )
        config_repository.create_source_asset(
            SourceAssetCreate(
                source_asset_id="bank_partner_transactions",
                source_system_id="bank_partner_export",
                dataset_contract_id="household_account_transactions_v1",
                column_mapping_id="bank_partner_export_v1",
                name="Bank Partner Transactions",
                asset_type="dataset",
                transformation_package_id="builtin_account_transactions",
            )
        )
        extension_registry = ExtensionRegistry()
        extension_registry.register(
            LayerExtension(
                layer="reporting",
                key="budget_projection_publication",
                kind="mart",
                description="Published budget projection relation.",
                module="tests.budget_projection_publication",
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
            )
        )
        config_repository.create_publication_definition(
            PublicationDefinitionCreate(
                publication_definition_id="pub_budget_projection",
                transformation_package_id="builtin_account_transactions",
                publication_key="mart_budget_projection",
                name="Budget projection",
            ),
            extension_registry=extension_registry,
        )
        transformation_service = TransformationService(
            DuckDBStore.open(str(temp_root / "warehouse.duckdb"))
        )
        reporting_service = ReportingService(
            transformation_service,
            publication_store=PostgresReportingStore(dsn),
            extension_registry=extension_registry,
        )
        client = TestClient(
            create_app(
                AccountTransactionService(
                    landing_root=temp_root / "landing",
                    metadata_repository=metadata_repository,
                ),
                extension_registry=extension_registry,
                config_repository=config_repository,
                transformation_service=transformation_service,
                reporting_service=reporting_service,
            )
        )

        response = client.post(
            "/ingest/configured-csv",
            json={
                "source_path": str(FIXTURES / "configured_account_transactions_source.csv"),
                "source_asset_id": "bank_partner_transactions",
                "source_system_id": "bank_partner_export",
                "dataset_contract_id": "household_account_transactions_v1",
                "column_mapping_id": "bank_partner_export_v1",
                "source_name": "manual-upload",
            },
        )

        assert response.status_code == 201
        assert "mart_budget_projection" in response.json()["promotion"]["publication_keys"]

        published_reporting_service = ReportingService(
            _FailingTransformationService(),  # type: ignore[arg-type]
            publication_store=PostgresReportingStore(dsn),
            extension_registry=extension_registry,
        )
        rows = published_reporting_service.get_relation_rows("mart_budget_projection")

    assert rows == [
        {
            "booking_month": "2026-01",
            "net": Decimal("2365.8500"),
        }
    ]
