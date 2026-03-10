from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast

from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.run_metadata import RunMetadataRepository

FIXTURES = Path(__file__).resolve().parent / "fixtures"


class _StubReportingService:
    def __init__(self) -> None:
        self.publications: list[list[str]] = []
        self.auxiliary_relations: list[list[str]] = []

    def get_monthly_cashflow(self, from_month=None, to_month=None):
        return [
            {
                "booking_month": "2026-01",
                "income": "2500.0000",
                "expense": "900.0000",
                "net": "1600.0000",
                "transaction_count": 2,
            }
        ]

    def get_current_dimension_rows(self, dimension_name: str):
        return []

    def get_transformation_audit(self, input_run_id=None):
        return [
            {
                "input_run_id": input_run_id or "run-001",
                "fact_rows": 2,
                "started_at": "2026-03-10T10:00:00+00:00",
                "completed_at": "2026-03-10T10:00:01+00:00",
            }
        ]

    def publish_publications(self, publication_keys: list[str]):
        self.publications.append(list(publication_keys))
        return publication_keys

    def publish_auxiliary_relations(self, relation_names: list[str]):
        self.auxiliary_relations.append(list(relation_names))
        return relation_names


class ReportingApiAppTests(unittest.TestCase):
    def test_monthly_cashflow_endpoint_can_use_reporting_service_without_transformation_service(
        self,
    ) -> None:
        with TemporaryDirectory() as temp_dir:
            service = AccountTransactionService(
                landing_root=Path(temp_dir) / "landing",
                metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
            )
            app = create_app(
                service,
                reporting_service=cast(Any, _StubReportingService()),
            )

            with TestClient(app) as client:
                response = client.get("/reports/monthly-cashflow")

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            [
                {
                    "booking_month": "2026-01",
                    "income": "2500.0000",
                    "expense": "900.0000",
                    "net": "1600.0000",
                    "transaction_count": 2,
                }
            ],
            response.json()["rows"],
        )

    def test_transformation_audit_endpoint_can_use_reporting_service_without_transformation_service(
        self,
    ) -> None:
        with TemporaryDirectory() as temp_dir:
            service = AccountTransactionService(
                landing_root=Path(temp_dir) / "landing",
                metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
            )
            app = create_app(
                service,
                reporting_service=cast(Any, _StubReportingService()),
            )

            with TestClient(app) as client:
                response = client.get(
                    "/transformation-audit",
                    params={"run_id": "run-123"},
                )

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            [
                {
                    "input_run_id": "run-123",
                    "fact_rows": 2,
                    "started_at": "2026-03-10T10:00:00+00:00",
                    "completed_at": "2026-03-10T10:00:01+00:00",
                }
            ],
            response.json()["audit"],
        )

    def test_reporting_extension_endpoint_can_use_reporting_service_without_transformation_service(
        self,
    ) -> None:
        with TemporaryDirectory() as temp_dir:
            service = AccountTransactionService(
                landing_root=Path(temp_dir) / "landing",
                metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
            )
            app = create_app(
                service,
                reporting_service=cast(Any, _StubReportingService()),
            )

            with TestClient(app) as client:
                response = client.get(
                    "/reports/monthly_cashflow_summary",
                    params={"run_id": "run-123"},
                )

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            [
                {
                    "booking_month": "2026-01",
                    "income": "2500.0000",
                    "expense": "900.0000",
                    "net": "1600.0000",
                    "transaction_count": 2,
                }
            ],
            response.json()["result"],
        )

    def test_ingest_endpoint_publishes_auxiliary_audit_relation_for_account_promotions(
        self,
    ) -> None:
        with TemporaryDirectory() as temp_dir:
            service = AccountTransactionService(
                landing_root=Path(temp_dir) / "landing",
                metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
            )
            reporting_service = _StubReportingService()
            app = create_app(
                service,
                transformation_service=TransformationService(DuckDBStore.memory()),
                reporting_service=cast(Any, reporting_service),
            )

            with TestClient(app) as client:
                response = client.post(
                    "/ingest",
                    json={
                        "source_path": str(FIXTURES / "account_transactions_valid.csv"),
                        "source_name": "reporting-sync-test",
                    },
                )

        self.assertEqual(201, response.status_code)
        self.assertEqual(
            [
                [
                    "mart_monthly_cashflow",
                    "mart_monthly_cashflow_by_counterparty",
                    "rpt_current_dim_account",
                    "rpt_current_dim_counterparty",
                ]
            ],
            reporting_service.publications,
        )
        self.assertEqual(
            [["transformation_audit"]],
            reporting_service.auxiliary_relations,
        )
