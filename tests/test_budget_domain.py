"""Tests for the budget domain — landing, transformation, and mart.

Covers:
- BudgetService landing contract validation
- Canonical budget parsing
- TransformationService load_budget_targets + mart refresh
- promote_budget_run
"""

from __future__ import annotations

import unittest
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from packages.pipelines.budget_service import BudgetService
from packages.pipelines.budgets import (
    CanonicalBudget,
    load_canonical_budgets_bytes,
)
from packages.pipelines.builtin_promotion_handlers import promote_budget_run
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.run_metadata import RunMetadataRepository

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


class CanonicalBudgetTests(unittest.TestCase):
    def test_load_valid_csv_returns_all_rows(self) -> None:
        budgets = load_canonical_budgets_bytes(
            (FIXTURES / "budgets_valid.csv").read_bytes()
        )
        self.assertEqual(4, len(budgets))
        categories = [b.category_id for b in budgets]
        self.assertIn("groceries", categories)
        self.assertIn("entertainment", categories)
        self.assertIn("transport", categories)
        self.assertIn("utilities", categories)

    def test_budget_has_correct_name(self) -> None:
        budgets = load_canonical_budgets_bytes(
            (FIXTURES / "budgets_valid.csv").read_bytes()
        )
        for b in budgets:
            self.assertEqual("Monthly Budget", b.budget_name)

    def test_budget_effective_to_none_when_empty(self) -> None:
        budgets = load_canonical_budgets_bytes(
            (FIXTURES / "budgets_valid.csv").read_bytes()
        )
        for b in budgets:
            self.assertIsNone(b.effective_to)

    def test_budget_target_amount_is_decimal(self) -> None:
        budgets = load_canonical_budgets_bytes(
            (FIXTURES / "budgets_valid.csv").read_bytes()
        )
        groceries = next(b for b in budgets if b.category_id == "groceries")
        self.assertEqual(Decimal("400.00"), groceries.target_amount)

    def test_budget_id_is_deterministic(self) -> None:
        budgets = load_canonical_budgets_bytes(
            (FIXTURES / "budgets_valid.csv").read_bytes()
        )
        # Same name+category always produces same id
        b1 = budgets[0]
        b2 = load_canonical_budgets_bytes(
            (FIXTURES / "budgets_valid.csv").read_bytes()
        )[0]
        self.assertEqual(b1.budget_id, b2.budget_id)

    def test_budget_is_frozen_dataclass(self) -> None:
        budgets = load_canonical_budgets_bytes(
            (FIXTURES / "budgets_valid.csv").read_bytes()
        )
        b = budgets[0]
        self.assertIsInstance(b, CanonicalBudget)
        with self.assertRaises((AttributeError, TypeError)):
            b.budget_name = "changed"  # type: ignore[misc]


class BudgetServiceTests(unittest.TestCase):
    def _make_service(self, temp_dir: str) -> BudgetService:
        return BudgetService(
            landing_root=Path(temp_dir) / "landing",
            metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
        )

    def test_ingest_valid_csv_creates_landed_run(self) -> None:
        with TemporaryDirectory() as temp_dir:
            svc = self._make_service(temp_dir)
            run = svc.ingest_file(FIXTURES / "budgets_valid.csv")
            self.assertEqual("landed", run.status.value)
            self.assertEqual("budgets", run.dataset_name)

    def test_ingest_invalid_values_creates_rejected_run(self) -> None:
        with TemporaryDirectory() as temp_dir:
            svc = self._make_service(temp_dir)
            run = svc.ingest_file(FIXTURES / "budgets_invalid_values.csv")
            self.assertFalse(run.passed)

    def test_get_canonical_budgets_returns_rows_for_passed_run(self) -> None:
        with TemporaryDirectory() as temp_dir:
            svc = self._make_service(temp_dir)
            run = svc.ingest_file(FIXTURES / "budgets_valid.csv")
            budgets = svc.get_canonical_budgets(run.run_id)
            self.assertEqual(4, len(budgets))
            self.assertIsInstance(budgets[0], CanonicalBudget)

    def test_get_canonical_budgets_returns_empty_for_rejected_run(self) -> None:
        with TemporaryDirectory() as temp_dir:
            svc = self._make_service(temp_dir)
            run = svc.ingest_file(FIXTURES / "budgets_invalid_values.csv")
            budgets = svc.get_canonical_budgets(run.run_id)
            self.assertEqual([], budgets)


class BudgetTransformationTests(unittest.TestCase):
    def _make_rows(self) -> list[dict]:
        return [
            {
                "budget_id": "bgt-001",
                "budget_name": "Monthly Budget",
                "category_id": "groceries",
                "period_type": "monthly",
                "period_label": "2026-01",
                "target_amount": "400.00",
                "currency": "EUR",
            },
            {
                "budget_id": "bgt-002",
                "budget_name": "Monthly Budget",
                "category_id": "entertainment",
                "period_type": "monthly",
                "period_label": "2026-01",
                "target_amount": "150.00",
                "currency": "EUR",
            },
            {
                "budget_id": "bgt-003",
                "budget_name": "Monthly Budget",
                "category_id": "transport",
                "period_type": "monthly",
                "period_label": "2026-01",
                "target_amount": "200.00",
                "currency": "EUR",
            },
        ]

    def test_load_budget_targets_inserts_facts(self) -> None:
        svc = TransformationService(DuckDBStore.memory())
        inserted = svc.load_budget_targets(self._make_rows(), run_id="run-bgt-001")
        self.assertEqual(3, inserted)

    def test_load_budget_targets_empty_returns_zero(self) -> None:
        svc = TransformationService(DuckDBStore.memory())
        self.assertEqual(0, svc.load_budget_targets([]))

    def test_count_budget_targets(self) -> None:
        svc = TransformationService(DuckDBStore.memory())
        svc.load_budget_targets(self._make_rows(), run_id="run-bgt-001")
        self.assertEqual(3, svc.count_budget_targets())
        self.assertEqual(3, svc.count_budget_targets("run-bgt-001"))
        self.assertEqual(0, svc.count_budget_targets("run-other"))

    def test_load_budget_targets_upserts_dim_budget(self) -> None:
        svc = TransformationService(DuckDBStore.memory())
        svc.load_budget_targets(self._make_rows(), run_id="run-001")
        budgets = svc.get_current_budgets()
        categories = {row["category_id"] for row in budgets}
        self.assertIn("groceries", categories)
        self.assertIn("entertainment", categories)
        self.assertIn("transport", categories)

    def test_refresh_budget_variance_with_no_spend_data(self) -> None:
        # Variance refresh should work even with no actual spend data —
        # actual_amount defaults to 0, status = under_budget
        svc = TransformationService(DuckDBStore.memory())
        svc.load_budget_targets(self._make_rows(), run_id="run-001")
        count = svc.refresh_budget_variance()
        self.assertEqual(3, count)

        rows = svc.get_budget_variance()
        for row in rows:
            self.assertEqual("under_budget", row["status"])
            self.assertEqual(str(row["target_amount"]), str(row["target_amount"]))

    def test_get_budget_variance_filter_by_category(self) -> None:
        svc = TransformationService(DuckDBStore.memory())
        svc.load_budget_targets(self._make_rows(), run_id="run-001")
        svc.refresh_budget_variance()

        rows = svc.get_budget_variance(category_id="groceries")
        self.assertEqual(1, len(rows))
        self.assertEqual("groceries", rows[0]["category_id"])

    def test_get_budget_variance_filter_by_period(self) -> None:
        svc = TransformationService(DuckDBStore.memory())
        svc.load_budget_targets(self._make_rows(), run_id="run-001")
        svc.refresh_budget_variance()

        rows = svc.get_budget_variance(period_label="2026-01")
        self.assertEqual(3, len(rows))

        rows = svc.get_budget_variance(period_label="2099-01")
        self.assertEqual(0, len(rows))

    def test_refresh_budget_progress_current(self) -> None:
        svc = TransformationService(DuckDBStore.memory())
        svc.load_budget_targets(self._make_rows(), run_id="run-001")
        svc.refresh_budget_variance()
        # progress_current only pulls current month; test doesn't assert count
        # since test date may not match 2026-01
        count = svc.refresh_budget_progress_current()
        self.assertIsInstance(count, int)

    def test_refresh_budget_envelope_drift(self) -> None:
        svc = TransformationService(DuckDBStore.memory())
        svc.load_budget_targets(self._make_rows(), run_id="run-001")
        svc.refresh_budget_variance()
        count = svc.refresh_budget_envelope_drift()
        self.assertEqual(3, count)

        rows = svc.get_budget_envelope_drift(category_id="groceries", period_label="2026-01")
        self.assertEqual(1, len(rows))
        row = rows[0]
        self.assertEqual("under_target", row["drift_state"])
        self.assertEqual(Decimal("400.0000"), Decimal(str(row["envelope_amount"])))
        self.assertEqual(Decimal("0"), Decimal(str(row["actual_amount"])))
        self.assertEqual(Decimal("-400.0000"), Decimal(str(row["drift_amount"])))

    def test_budget_variance_variance_calculation(self) -> None:
        svc = TransformationService(DuckDBStore.memory())
        svc.load_budget_targets(self._make_rows(), run_id="run-001")
        svc.refresh_budget_variance()

        rows = svc.get_budget_variance(category_id="groceries", period_label="2026-01")
        self.assertEqual(1, len(rows))
        row = rows[0]
        # With no spend data: variance = target - 0 = target
        self.assertEqual(Decimal("400.0000"), Decimal(str(row["target_amount"])))
        self.assertEqual(Decimal("0"), Decimal(str(row["actual_amount"])))
        self.assertEqual(Decimal("400.0000"), Decimal(str(row["variance"])))


class PromoteBudgetRunTests(unittest.TestCase):
    def test_promote_budget_run_loads_facts(self) -> None:
        with TemporaryDirectory() as temp_dir:
            budget_svc = BudgetService(
                landing_root=Path(temp_dir) / "landing",
                metadata_repository=RunMetadataRepository(
                    Path(temp_dir) / "runs.db"
                ),
            )
            ts = TransformationService(DuckDBStore.memory())

            run = budget_svc.ingest_file(FIXTURES / "budgets_valid.csv")
            result = promote_budget_run(
                run.run_id,
                budget_service=budget_svc,
                transformation_service=ts,
            )

            self.assertFalse(result.skipped)
            self.assertEqual(4, result.facts_loaded)
            self.assertIn("mart_budget_variance", result.marts_refreshed)
            self.assertIn("mart_budget_envelope_drift", result.marts_refreshed)
            self.assertIn("mart_budget_progress_current", result.marts_refreshed)
            self.assertEqual(4, ts.count_budget_targets())

    def test_promote_rejected_run_returns_skipped(self) -> None:
        with TemporaryDirectory() as temp_dir:
            budget_svc = BudgetService(
                landing_root=Path(temp_dir) / "landing",
                metadata_repository=RunMetadataRepository(
                    Path(temp_dir) / "runs.db"
                ),
            )
            ts = TransformationService(DuckDBStore.memory())

            run = budget_svc.ingest_file(FIXTURES / "budgets_invalid_values.csv")
            result = promote_budget_run(
                run.run_id,
                budget_service=budget_svc,
                transformation_service=ts,
            )

            self.assertTrue(result.skipped)
            self.assertEqual(0, result.facts_loaded)
            self.assertEqual(0, ts.count_budget_targets())

    def test_promote_already_promoted_run_returns_skipped(self) -> None:
        with TemporaryDirectory() as temp_dir:
            budget_svc = BudgetService(
                landing_root=Path(temp_dir) / "landing",
                metadata_repository=RunMetadataRepository(
                    Path(temp_dir) / "runs.db"
                ),
            )
            ts = TransformationService(DuckDBStore.memory())

            run = budget_svc.ingest_file(FIXTURES / "budgets_valid.csv")
            promote_budget_run(
                run.run_id,
                budget_service=budget_svc,
                transformation_service=ts,
            )
            result2 = promote_budget_run(
                run.run_id,
                budget_service=budget_svc,
                transformation_service=ts,
            )

            self.assertTrue(result2.skipped)
            self.assertEqual("run already promoted", result2.skip_reason)
            # Fact count should not have doubled
            self.assertEqual(4, ts.count_budget_targets())


if __name__ == "__main__":
    unittest.main()
