from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from packages.pipelines.contract_price_service import ContractPriceService
from packages.pipelines.contract_prices import (
    CanonicalContractPrice,
    load_canonical_contract_prices_bytes,
)
from packages.pipelines.promotion import promote_contract_price_run
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.run_metadata import RunMetadataRepository


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


class CanonicalContractPriceTests(unittest.TestCase):
    def test_load_valid_csv_returns_rows(self) -> None:
        rows = load_canonical_contract_prices_bytes(
            (FIXTURES / "contract_prices_valid.csv").read_bytes()
        )
        self.assertEqual(4, len(rows))
        self.assertIsInstance(rows[0], CanonicalContractPrice)

    def test_electricity_row_keeps_quantity_unit(self) -> None:
        rows = load_canonical_contract_prices_bytes(
            (FIXTURES / "contract_prices_valid.csv").read_bytes()
        )
        energy = next(row for row in rows if row.price_component == "energy")
        self.assertEqual("electricity", energy.contract_type)
        self.assertEqual("kWh", energy.quantity_unit)


class ContractPriceServiceTests(unittest.TestCase):
    def _make_service(self, temp_dir: str) -> ContractPriceService:
        return ContractPriceService(
            landing_root=Path(temp_dir) / "landing",
            metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
        )

    def test_ingest_valid_csv_creates_landed_run(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = self._make_service(temp_dir)
            run = service.ingest_file(FIXTURES / "contract_prices_valid.csv")
            self.assertEqual("landed", run.status.value)
            self.assertEqual("contract_prices", run.dataset_name)

    def test_ingest_invalid_values_creates_rejected_run(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = self._make_service(temp_dir)
            run = service.ingest_file(FIXTURES / "contract_prices_invalid_values.csv")
            self.assertFalse(run.passed)


class ContractPriceTransformationTests(unittest.TestCase):
    def _make_rows(self) -> list[dict]:
        return [
            {
                "contract_id": "c-electricity",
                "contract_name": "Helen Spot",
                "provider": "Helen",
                "contract_type": "electricity",
                "price_component": "energy",
                "billing_cycle": "per_kwh",
                "unit_price": "0.0825",
                "currency": "EUR",
                "quantity_unit": "kWh",
                "valid_from": "2026-01-01",
                "valid_to": None,
            },
            {
                "contract_id": "c-broadband",
                "contract_name": "Fiber 1000",
                "provider": "ISP Oy",
                "contract_type": "broadband",
                "price_component": "monthly_fee",
                "billing_cycle": "monthly",
                "unit_price": "39.90",
                "currency": "EUR",
                "quantity_unit": None,
                "valid_from": "2025-06-01",
                "valid_to": None,
            },
        ]

    def test_load_contract_prices_inserts_facts(self) -> None:
        service = TransformationService(DuckDBStore.memory())
        inserted = service.load_contract_prices(self._make_rows(), run_id="run-price-001")
        self.assertEqual(2, inserted)
        self.assertEqual(2, service.count_contract_prices())

    def test_refresh_current_price_marts(self) -> None:
        service = TransformationService(DuckDBStore.memory())
        service.load_contract_prices(self._make_rows(), run_id="run-price-001")
        service.refresh_contract_price_current()

        current_rows = service.get_contract_price_current()
        self.assertEqual(2, len(current_rows))

        electricity_rows = service.get_electricity_price_current()
        self.assertEqual(1, len(electricity_rows))
        self.assertEqual("Helen Spot", electricity_rows[0]["contract_name"])
        self.assertEqual(Decimal("0.0825"), Decimal(electricity_rows[0]["unit_price"]))


class PromoteContractPriceRunTests(unittest.TestCase):
    def test_promote_contract_price_run_loads_facts(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = ContractPriceService(
                landing_root=Path(temp_dir) / "landing",
                metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
            )
            transformation_service = TransformationService(DuckDBStore.memory())

            run = service.ingest_file(FIXTURES / "contract_prices_valid.csv")
            result = promote_contract_price_run(
                run.run_id,
                contract_price_service=service,
                transformation_service=transformation_service,
            )

            self.assertFalse(result.skipped)
            self.assertEqual(4, result.facts_loaded)
            self.assertIn("mart_contract_price_current", result.marts_refreshed)
            self.assertIn("mart_electricity_price_current", result.marts_refreshed)
            self.assertIn("mart_electricity_price_current", result.publication_keys)


if __name__ == "__main__":
    unittest.main()
