from __future__ import annotations

import unittest
from datetime import date, datetime, timezone

from packages.pipelines.normalization import (
    MeasurementUnit,
    normalize_currency_code,
    normalize_timestamp_utc,
    normalize_unit,
)
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore


class TransformationNormalizationTests(unittest.TestCase):
    def test_normalize_timestamp_utc_handles_date_and_offset_datetime(self) -> None:
        self.assertEqual(
            datetime(2026, 1, 2, 0, 0, tzinfo=timezone.utc),
            normalize_timestamp_utc("2026-01-02"),
        )
        self.assertEqual(
            datetime(2026, 1, 2, 7, 15, tzinfo=timezone.utc),
            normalize_timestamp_utc("2026-01-02T09:15:00+02:00"),
        )

    def test_normalize_currency_and_unit_values(self) -> None:
        self.assertEqual("EUR", normalize_currency_code(" eur "))
        self.assertEqual(MeasurementUnit.KWH, normalize_unit("kWh"))
        self.assertEqual(MeasurementUnit.LITER, normalize_unit("litres"))

    def test_transformation_service_persists_normalized_transaction_fields(self) -> None:
        service = TransformationService(DuckDBStore.memory())

        inserted = service.load_transactions(
            [
                {
                    "booked_at": "2026-01-02T09:15:00+02:00",
                    "account_id": "CHK-001",
                    "counterparty_name": "Electric Utility",
                    "amount": "-84.15",
                    "currency": "eur",
                    "description": "Monthly bill",
                },
                {
                    "booked_at": "2026-01-03",
                    "account_id": "CHK-001",
                    "counterparty_name": "Employer",
                    "amount": "2450.00",
                    "currency": "EUR",
                    "description": "Salary",
                },
            ],
            run_id="run-001",
        )

        self.assertEqual(2, inserted)
        facts = service.get_transactions()
        first = next(
            row for row in facts if row["counterparty_name"] == "Electric Utility"
        )
        second = next(row for row in facts if row["counterparty_name"] == "Employer")

        self.assertEqual("eur", first["currency"])
        self.assertEqual("EUR", first["normalized_currency"])
        self.assertEqual(
            datetime(2026, 1, 2, 7, 15, tzinfo=timezone.utc),
            first["booked_at_utc"],
        )
        self.assertEqual(date(2026, 1, 2), first["booked_at"])
        self.assertEqual("EUR", second["normalized_currency"])
        self.assertEqual(
            datetime(2026, 1, 3, 0, 0, tzinfo=timezone.utc),
            second["booked_at_utc"],
        )

    def test_current_dimension_views_return_one_row_per_natural_key(self) -> None:
        service = TransformationService(DuckDBStore.memory())

        service.load_transactions(
            [
                {
                    "booked_at": "2026-01-02",
                    "account_id": "CHK-001",
                    "counterparty_name": "Electric Utility",
                    "amount": "-84.15",
                    "currency": "EUR",
                    "description": "Monthly bill",
                },
                {
                    "booked_at": "2026-01-03",
                    "account_id": "SAV-001",
                    "counterparty_name": "Employer",
                    "amount": "2450.00",
                    "currency": "EUR",
                    "description": "Salary",
                },
            ],
            effective_date=date(2026, 1, 1),
        )
        service.load_transactions(
            [
                {
                    "booked_at": "2026-02-02",
                    "account_id": "CHK-001",
                    "counterparty_name": "Electric Utility",
                    "amount": "-84.15",
                    "currency": "USD",
                    "description": "Monthly bill",
                }
            ],
            effective_date=date(2026, 2, 1),
        )

        accounts = service.get_current_dimension_rows("dim_account")

        self.assertEqual(2, len(accounts))
        by_account_id = {row["account_id"]: row for row in accounts}
        self.assertEqual("USD", by_account_id["CHK-001"]["currency"])
        self.assertEqual("EUR", by_account_id["SAV-001"]["currency"])


if __name__ == "__main__":
    unittest.main()
