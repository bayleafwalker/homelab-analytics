from __future__ import annotations

import io
import json
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi.testclient import TestClient

from apps.api.app import create_app
from apps.worker.main import main
from packages.domains.finance.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.transformation_service import TransformationService
from packages.pipelines.utility_bills import (
    CanonicalUtilityBill,
    load_canonical_utility_bills_bytes,
)
from packages.pipelines.utility_models import DIM_METER
from packages.pipelines.utility_usage import (
    CanonicalUtilityUsage,
    load_canonical_utility_usage_bytes,
)
from packages.shared.settings import AppSettings
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.run_metadata import RunMetadataRepository
from tests.utility_test_support import (
    FIXTURES,
    UTILITY_BILLS_ASSET_ID,
    UTILITY_BILLS_CONTRACT_ID,
    UTILITY_BILLS_MAPPING_ID,
    UTILITY_SOURCE_SYSTEM_ID,
    UTILITY_USAGE_ASSET_ID,
    UTILITY_USAGE_CONTRACT_ID,
    UTILITY_USAGE_MAPPING_ID,
    create_utility_configuration,
)

pytestmark = [pytest.mark.integration]


class CanonicalUtilityTests(unittest.TestCase):
    def test_load_canonical_utility_usage_bytes_returns_rows(self) -> None:
        rows = load_canonical_utility_usage_bytes(
            (
                "meter_id,meter_name,utility_type,location,usage_start,usage_end,"
                "usage_quantity,usage_unit,reading_source\n"
                "elec-001,Main Apartment Meter,electricity,home,2026-01-01,2026-01-31,"
                "320.50,kWh,smart-meter\n"
            ).encode("utf-8")
        )

        self.assertEqual(1, len(rows))
        self.assertIsInstance(rows[0], CanonicalUtilityUsage)
        self.assertEqual("kwh", rows[0].usage_unit)

    def test_load_canonical_utility_bills_bytes_returns_rows(self) -> None:
        rows = load_canonical_utility_bills_bytes(
            (
                "meter_id,meter_name,provider,utility_type,location,billing_period_start,"
                "billing_period_end,billed_amount,currency,billed_quantity,usage_unit,"
                "invoice_date\n"
                "elec-001,Main Apartment Meter,City Power,electricity,home,2026-01-01,"
                "2026-01-31,48.08,eur,320.50,kWh,2026-02-05\n"
            ).encode("utf-8")
        )

        self.assertEqual(1, len(rows))
        self.assertIsInstance(rows[0], CanonicalUtilityBill)
        self.assertEqual("EUR", rows[0].currency)
        self.assertEqual("kwh", rows[0].usage_unit)

    def test_canonical_utility_usage_rejects_unsupported_unit(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported unit value"):
            load_canonical_utility_usage_bytes(
                (
                    "meter_id,meter_name,utility_type,location,usage_start,usage_end,"
                    "usage_quantity,usage_unit,reading_source\n"
                    "water-001,Cold Water Meter,water,home,2026-01-01,2026-01-31,"
                    "12700.00,m3,manual-read\n"
                ).encode("utf-8")
            )


class UtilityTransformationTests(unittest.TestCase):
    def _make_usage_rows(self) -> list[dict[str, object]]:
        return [
            {
                "meter_id": "elec-001",
                "meter_name": "Main Apartment Meter",
                "utility_type": "electricity",
                "location": "home",
                "usage_start": "2026-01-01",
                "usage_end": "2026-01-31",
                "usage_quantity": "320.50",
                "usage_unit": "kWh",
                "reading_source": "smart-meter",
            },
            {
                "meter_id": "elec-001",
                "meter_name": "Main Apartment Meter",
                "utility_type": "electricity",
                "location": "home",
                "usage_start": "2026-02-01",
                "usage_end": "2026-02-28",
                "usage_quantity": "298.40",
                "usage_unit": "kWh",
                "reading_source": "smart-meter",
            },
            {
                "meter_id": "water-001",
                "meter_name": "Cold Water Meter",
                "utility_type": "water",
                "location": "home",
                "usage_start": "2026-01-01",
                "usage_end": "2026-01-31",
                "usage_quantity": "12700.00",
                "usage_unit": "liter",
                "reading_source": "manual-read",
            },
        ]

    def _make_bill_rows(self) -> list[dict[str, object]]:
        return [
            {
                "meter_id": "elec-001",
                "meter_name": "Main Apartment Meter",
                "provider": "City Power",
                "utility_type": "electricity",
                "location": "home",
                "billing_period_start": "2026-01-01",
                "billing_period_end": "2026-01-31",
                "billed_amount": "48.08",
                "currency": "EUR",
                "billed_quantity": "320.50",
                "usage_unit": "kWh",
                "invoice_date": "2026-02-05",
            },
            {
                "meter_id": "water-001",
                "meter_name": "Cold Water Meter",
                "provider": "City Water",
                "utility_type": "water",
                "location": "home",
                "billing_period_start": "2026-02-01",
                "billing_period_end": "2026-02-28",
                "billed_amount": "19.35",
                "currency": "EUR",
                "billed_quantity": "11900.00",
                "usage_unit": "liter",
                "invoice_date": "2026-03-03",
            },
        ]

    def test_load_utility_usage_and_bills_insert_facts(self) -> None:
        service = TransformationService(DuckDBStore.memory())

        usage_inserted = service.load_utility_usage(
            self._make_usage_rows(),
            run_id="run-usage-001",
        )
        bill_inserted = service.load_bills(
            self._make_bill_rows(),
            run_id="run-bill-001",
        )

        self.assertEqual(3, usage_inserted)
        self.assertEqual(2, bill_inserted)
        self.assertEqual(3, service.count_utility_usage())
        self.assertEqual(2, service.count_bills())

    def test_refresh_utility_cost_summary_covers_matched_usage_only_and_bill_only_rows(
        self,
    ) -> None:
        service = TransformationService(DuckDBStore.memory())
        service.load_utility_usage(self._make_usage_rows(), run_id="run-usage-001")
        service.load_bills(self._make_bill_rows(), run_id="run-bill-001")

        count = service.refresh_utility_cost_summary()
        rows = service.get_utility_cost_summary()

        self.assertEqual(4, count)
        self.assertEqual(4, len(rows))
        coverage = {(row["period"], row["meter_id"]): row["coverage_status"] for row in rows}
        self.assertEqual("matched", coverage[("2026-01", "elec-001")])
        self.assertEqual("usage_only", coverage[("2026-01", "water-001")])
        self.assertEqual("usage_only", coverage[("2026-02", "elec-001")])
        self.assertEqual("bill_only", coverage[("2026-02", "water-001")])

        matched_row = next(
            row
            for row in rows
            if row["period"] == "2026-01" and row["meter_id"] == "elec-001"
        )
        self.assertEqual(Decimal("48.0800"), Decimal(matched_row["billed_amount"]))
        self.assertEqual(Decimal("320.5000"), Decimal(matched_row["usage_quantity"]))
        self.assertAlmostEqual(0.15, float(matched_row["unit_cost"]), places=4)

    def test_utility_cost_summary_filters_and_granularity(self) -> None:
        service = TransformationService(DuckDBStore.memory())
        service.load_utility_usage(self._make_usage_rows(), run_id="run-usage-001")
        service.load_bills(self._make_bill_rows(), run_id="run-bill-001")
        service.refresh_utility_cost_summary()

        electricity_rows = service.get_utility_cost_summary(utility_type="electricity")
        self.assertEqual(2, len(electricity_rows))

        meter_rows = service.get_utility_cost_summary(
            meter_id="water-001",
            from_period="2026-01-01",
            to_period="2026-02-28",
            granularity="day",
        )
        self.assertEqual(2, len(meter_rows))
        self.assertEqual(
            {"2026-01-01", "2026-02-01"},
            {row["period"].isoformat() for row in meter_rows},
        )

        with self.assertRaisesRegex(ValueError, "Unsupported granularity"):
            service.get_utility_cost_summary(granularity="quarter")

    def test_meter_dimension_uses_scd_for_attribute_changes(self) -> None:
        service = TransformationService(DuckDBStore.memory())
        service.load_utility_usage(
            [
                {
                    "meter_id": "elec-001",
                    "meter_name": "Main Apartment Meter",
                    "utility_type": "electricity",
                    "location": "home",
                    "usage_start": "2026-01-01",
                    "usage_end": "2026-01-31",
                    "usage_quantity": "320.50",
                    "usage_unit": "kWh",
                    "reading_source": "smart-meter",
                }
            ],
            run_id="run-usage-001",
            effective_date=date(2026, 1, 1),
        )
        service.load_utility_usage(
            [
                {
                    "meter_id": "elec-001",
                    "meter_name": "Main Apartment Meter v2",
                    "utility_type": "electricity",
                    "location": "home",
                    "usage_start": "2026-02-01",
                    "usage_end": "2026-02-28",
                    "usage_quantity": "298.40",
                    "usage_unit": "kWh",
                    "reading_source": "smart-meter",
                }
            ],
            run_id="run-usage-002",
            effective_date=date(2026, 2, 1),
        )

        current = service.get_current_meters()
        history = service.store.fetchall_dicts(
            f"SELECT * FROM {DIM_METER.table_name} ORDER BY valid_from"
        )

        self.assertEqual(1, len(current))
        self.assertEqual("Main Apartment Meter v2", current[0]["meter_name"])
        self.assertEqual(2, len(history))
        self.assertEqual("Main Apartment Meter", history[0]["meter_name"])
        self.assertEqual(date(2026, 2, 1), history[0]["valid_to"])


class ConfiguredUtilityApiTests(unittest.TestCase):
    def _build_client(self, temp_dir: str) -> tuple[TestClient, TransformationService]:
        config_repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
        create_utility_configuration(config_repository)
        transformation_service = TransformationService(
            DuckDBStore.open(str(Path(temp_dir) / "warehouse.duckdb"))
        )
        client = TestClient(
            create_app(
                AccountTransactionService(
                    landing_root=Path(temp_dir) / "landing",
                    metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
                ),
                config_repository=config_repository,
                transformation_service=transformation_service,
            )
        )
        return client, transformation_service

    def test_configured_utility_ingestion_promotes_and_reports_end_to_end(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client, transformation_service = self._build_client(temp_dir)

            usage_response = client.post(
                "/ingest/configured-csv",
                json={
                    "source_path": str(FIXTURES / "utility_usage_source.csv"),
                    "source_asset_id": UTILITY_USAGE_ASSET_ID,
                    "source_system_id": UTILITY_SOURCE_SYSTEM_ID,
                    "dataset_contract_id": UTILITY_USAGE_CONTRACT_ID,
                    "column_mapping_id": UTILITY_USAGE_MAPPING_ID,
                    "source_name": "manual-upload",
                },
            )
            self.assertEqual(201, usage_response.status_code)
            self.assertEqual(3, usage_response.json()["promotion"]["facts_loaded"])

            bill_response = client.post(
                "/ingest/configured-csv",
                json={
                    "source_path": str(FIXTURES / "utility_bills_source.csv"),
                    "source_asset_id": UTILITY_BILLS_ASSET_ID,
                    "source_system_id": UTILITY_SOURCE_SYSTEM_ID,
                    "dataset_contract_id": UTILITY_BILLS_CONTRACT_ID,
                    "column_mapping_id": UTILITY_BILLS_MAPPING_ID,
                    "source_name": "manual-upload",
                },
            )
            self.assertEqual(201, bill_response.status_code)
            self.assertEqual(2, bill_response.json()["promotion"]["facts_loaded"])
            self.assertEqual(3, transformation_service.count_utility_usage())
            self.assertEqual(2, transformation_service.count_bills())

            report_response = client.get("/reports/utility-cost-summary")
            self.assertEqual(200, report_response.status_code)
            rows = report_response.json()["rows"]
            self.assertEqual(4, len(rows))
            self.assertEqual(
                {"matched", "usage_only", "bill_only"},
                {row["coverage_status"] for row in rows},
            )

            filtered_response = client.get(
                "/reports/utility-cost-summary",
                params={
                    "utility_type": "electricity",
                    "meter_id": "elec-001",
                    "from_period": "2026-01-01",
                    "to_period": "2026-02-28",
                    "granularity": "day",
                },
            )
            self.assertEqual(200, filtered_response.status_code)
            filtered_rows = filtered_response.json()["rows"]
            self.assertEqual(2, len(filtered_rows))
            self.assertEqual(
                {"2026-01-01", "2026-02-01"},
                {row["period"] for row in filtered_rows},
            )

    def test_configured_utility_ingestion_rejects_invalid_source_rows(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client, _ = self._build_client(temp_dir)

            usage_response = client.post(
                "/ingest/configured-csv",
                json={
                    "source_path": str(FIXTURES / "utility_usage_invalid_source.csv"),
                    "source_asset_id": UTILITY_USAGE_ASSET_ID,
                    "source_system_id": UTILITY_SOURCE_SYSTEM_ID,
                    "dataset_contract_id": UTILITY_USAGE_CONTRACT_ID,
                    "column_mapping_id": UTILITY_USAGE_MAPPING_ID,
                    "source_name": "manual-upload",
                },
            )
            self.assertEqual(400, usage_response.status_code)
            self.assertEqual("rejected", usage_response.json()["run"]["status"])

            bill_response = client.post(
                "/ingest/configured-csv",
                json={
                    "source_path": str(FIXTURES / "utility_bills_invalid_source.csv"),
                    "source_asset_id": UTILITY_BILLS_ASSET_ID,
                    "source_system_id": UTILITY_SOURCE_SYSTEM_ID,
                    "dataset_contract_id": UTILITY_BILLS_CONTRACT_ID,
                    "column_mapping_id": UTILITY_BILLS_MAPPING_ID,
                    "source_name": "manual-upload",
                },
            )
            self.assertEqual(400, bill_response.status_code)
            self.assertEqual("rejected", bill_response.json()["run"]["status"])


class ConfiguredUtilityWorkerTests(unittest.TestCase):
    def _make_settings(self, temp_dir: str) -> AppSettings:
        return AppSettings(
            data_dir=Path(temp_dir),
            landing_root=Path(temp_dir) / "landing",
            metadata_database_path=Path(temp_dir) / "metadata" / "runs.db",
            account_transactions_inbox_dir=Path(temp_dir) / "inbox" / "account-transactions",
            processed_files_dir=Path(temp_dir) / "processed" / "account-transactions",
            failed_files_dir=Path(temp_dir) / "failed" / "account-transactions",
            analytics_database_path=Path(temp_dir) / "analytics" / "warehouse.duckdb",
            config_database_path=Path(temp_dir) / "config.db",
            api_host="0.0.0.0",
            api_port=8080,
            web_host="0.0.0.0",
            web_port=8081,
            worker_poll_interval_seconds=1,
        )

    def test_worker_configured_utility_commands_emit_report_rows(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = self._make_settings(temp_dir)
            config_repository = IngestionConfigRepository(settings.resolved_config_database_path)
            create_utility_configuration(config_repository)
            stdout = io.StringIO()
            stderr = io.StringIO()

            usage_exit = main(
                [
                    "ingest-configured-csv",
                    str(FIXTURES / "utility_usage_source.csv"),
                    "--source-asset-id",
                    UTILITY_USAGE_ASSET_ID,
                    "--source-name",
                    "manual-upload",
                ],
                stdout=stdout,
                stderr=stderr,
                settings=settings,
            )
            self.assertEqual(0, usage_exit)
            usage_payload = json.loads(stdout.getvalue())
            self.assertEqual(3, usage_payload["promotion"]["facts_loaded"])

            stdout = io.StringIO()
            bills_exit = main(
                [
                    "ingest-configured-csv",
                    str(FIXTURES / "utility_bills_source.csv"),
                    "--source-asset-id",
                    UTILITY_BILLS_ASSET_ID,
                    "--source-name",
                    "manual-upload",
                ],
                stdout=stdout,
                stderr=stderr,
                settings=settings,
            )
            self.assertEqual(0, bills_exit)
            bill_payload = json.loads(stdout.getvalue())
            self.assertEqual(2, bill_payload["promotion"]["facts_loaded"])

            stdout = io.StringIO()
            report_exit = main(
                [
                    "report-utility-cost-summary",
                    "--utility-type",
                    "electricity",
                    "--granularity",
                    "month",
                ],
                stdout=stdout,
                stderr=stderr,
                settings=settings,
            )
            self.assertEqual(0, report_exit)
            report_payload = json.loads(stdout.getvalue())
            self.assertEqual(2, len(report_payload["rows"]))
            self.assertEqual(
                {"matched", "usage_only"},
                {row["coverage_status"] for row in report_payload["rows"]},
            )

    def test_worker_configured_utility_ingestion_surfaces_invalid_units(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = self._make_settings(temp_dir)
            config_repository = IngestionConfigRepository(settings.resolved_config_database_path)
            create_utility_configuration(config_repository)
            invalid_source = Path(temp_dir) / "utility_usage_invalid_unit.csv"
            invalid_source.write_text(
                (
                    "meter_ref,meter_label,utility_kind,site_label,period_start,period_end,"
                    "consumption,unit_code,source_system\n"
                    "water-001,Cold Water Meter,water,home,2026-01-01,2026-01-31,"
                    "12700.00,m3,manual-read\n"
                )
            )
            stdout = io.StringIO()
            stderr = io.StringIO()

            exit_code = main(
                [
                    "ingest-configured-csv",
                    str(invalid_source),
                    "--source-asset-id",
                    UTILITY_USAGE_ASSET_ID,
                    "--source-name",
                    "manual-upload",
                ],
                stdout=stdout,
                stderr=stderr,
                settings=settings,
            )

            self.assertEqual(1, exit_code)
            self.assertIn("Unsupported unit value", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
