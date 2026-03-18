from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

import psycopg
import pytest

from packages.pipelines.configured_csv_ingestion import ConfiguredCsvIngestionService
from packages.pipelines.promotion import promote_source_asset_run
from packages.pipelines.reporting_service import (
    ReportingAccessMode,
    ReportingService,
    publish_promotion_reporting,
)
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.postgres_ingestion_config import PostgresIngestionConfigRepository
from packages.storage.postgres_reporting import PostgresReportingStore
from packages.storage.run_metadata import RunMetadataRepository
from packages.storage.s3_blob import S3BlobStore
from tests.control_plane_test_support import seed_source_asset_graph
from tests.minio_test_support import running_minio_container
from tests.postgres_test_support import running_postgres_container

pytestmark = [pytest.mark.integration, pytest.mark.slow]
ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


class _FailingTransformationService:
    def get_monthly_cashflow(self, *args, **kwargs):
        raise AssertionError("published reporting path should not read from DuckDB")


def test_s3_landing_postgres_control_plane_and_postgres_publication_work_end_to_end() -> None:
    with (
        TemporaryDirectory() as temp_dir,
        running_postgres_container() as dsn,
        running_minio_container() as minio,
    ):
        temp_root = Path(temp_dir)
        metadata_repository = RunMetadataRepository(temp_root / "runs.db")
        control_repository = PostgresIngestionConfigRepository(dsn, schema="control")
        seeded = seed_source_asset_graph(
            control_repository,
            include_schedule=False,
            include_lineage=False,
            include_audit=False,
        )
        blob_store = S3BlobStore(
            bucket=minio.bucket,
            endpoint_url=minio.endpoint_url,
            region_name=minio.region_name,
            access_key_id=minio.access_key_id,
            secret_access_key=minio.secret_access_key,
            prefix="bronze",
        )
        ingestion_service = ConfiguredCsvIngestionService(
            landing_root=temp_root / "landing",
            metadata_repository=metadata_repository,
            config_repository=control_repository,
            blob_store=blob_store,
        )
        transformation_service = TransformationService(
            DuckDBStore.open(str(temp_root / "warehouse.duckdb")),
            control_plane_store=control_repository,
        )
        reporting_service = ReportingService(
            transformation_service,
            publication_store=PostgresReportingStore(dsn, schema="reporting"),
            access_mode=ReportingAccessMode.PUBLISHED,
            control_plane_store=control_repository,
        )

        run = ingestion_service.ingest_file(
            FIXTURES / "configured_account_transactions_source.csv",
            source_system_id=seeded["source_system"].source_system_id,
            dataset_contract_id=seeded["dataset_contract"].dataset_contract_id,
            column_mapping_id=seeded["column_mapping"].column_mapping_id,
            source_name="bank-minio",
        )
        promotion = promote_source_asset_run(
            run.run_id,
            source_asset=seeded["source_asset"],
            config_repository=control_repository,
            landing_root=temp_root / "landing",
            metadata_repository=metadata_repository,
            transformation_service=transformation_service,
            blob_store=blob_store,
        )
        published = publish_promotion_reporting(reporting_service, promotion)

        assert run.raw_path.startswith("s3://landing/bronze/")
        assert promotion.skipped is False
        assert set(published) == {
            "mart_monthly_cashflow",
            "mart_monthly_cashflow_by_counterparty",
            "rpt_current_dim_account",
            "rpt_current_dim_counterparty",
            "mart_spend_by_category_monthly",
            "mart_recent_large_transactions",
            "transformation_audit",
        }

        published_reader = ReportingService(
            _FailingTransformationService(),  # type: ignore[arg-type]
            publication_store=PostgresReportingStore(dsn, schema="reporting"),
            access_mode=ReportingAccessMode.PUBLISHED,
            control_plane_store=control_repository,
        )
        assert published_reader.get_monthly_cashflow() == [
            {
                "booking_month": "2026-01",
                "income": Decimal("2450.0000"),
                "expense": Decimal("84.1500"),
                "net": Decimal("2365.8500"),
                "transaction_count": 2,
            }
        ]

        current_account_rows = transformation_service.store.fetchall_dicts(
            """
            SELECT account_id, source_system, source_run_id
            FROM dim_account
            WHERE is_current = TRUE
            ORDER BY account_id
            """
        )
        assert current_account_rows == [
            {
                "account_id": "CHK-001",
                "source_system": "bank-minio",
                "source_run_id": run.run_id,
            }
        ]

        lineage = control_repository.list_source_lineage(input_run_id=run.run_id)
        assert {"reporting", "transformation"} == {
            record.target_layer for record in lineage
        }
        assert "fact_transaction" in {record.target_name for record in lineage}
        assert "mart_monthly_cashflow" in {record.target_name for record in lineage}

        audit = control_repository.list_publication_audit(run_id=run.run_id)
        assert {record.publication_key for record in audit} == set(published)

        with psycopg.connect(dsn) as connection:
            rows = connection.execute(
                """
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE (table_schema = 'control' AND table_name = 'source_systems')
                   OR (table_schema = 'reporting' AND table_name = 'mart_monthly_cashflow')
                ORDER BY table_schema, table_name
                """
            ).fetchall()
        assert rows == [
            ("control", "source_systems"),
            ("reporting", "mart_monthly_cashflow"),
        ]
