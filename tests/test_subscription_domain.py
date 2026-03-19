"""Tests for the subscription domain — landing, transformation, and mart.

Covers:
- SubscriptionService landing contract validation
- Canonical subscription parsing
- TransformationService load_subscriptions + mart refresh
- promote_subscription_run
"""

from __future__ import annotations

import unittest
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from packages.pipelines.promotion import promote_subscription_run
from packages.pipelines.subscription_service import SubscriptionService
from packages.pipelines.subscriptions import (
    CanonicalSubscription,
    load_canonical_subscriptions_bytes,
)
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.run_metadata import RunMetadataRepository

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


class CanonicalSubscriptionTests(unittest.TestCase):
    def test_load_valid_csv_returns_all_rows(self) -> None:
        subs = load_canonical_subscriptions_bytes(
            (FIXTURES / "subscriptions_valid.csv").read_bytes()
        )
        self.assertEqual(5, len(subs))
        names = [s.service_name for s in subs]
        self.assertIn("Netflix", names)
        self.assertIn("Spotify", names)
        self.assertIn("GitHub Pro", names)

    def test_active_subscription_has_no_end_date(self) -> None:
        subs = load_canonical_subscriptions_bytes(
            (FIXTURES / "subscriptions_valid.csv").read_bytes()
        )
        netflix = next(s for s in subs if s.service_name == "Netflix")
        self.assertIsNone(netflix.end_date)

    def test_inactive_subscription_has_end_date(self) -> None:
        subs = load_canonical_subscriptions_bytes(
            (FIXTURES / "subscriptions_valid.csv").read_bytes()
        )
        adobe = next(s for s in subs if s.service_name == "Adobe Creative Cloud")
        self.assertIsNotNone(adobe.end_date)

    def test_monthly_equivalent_for_monthly_billing(self) -> None:
        subs = load_canonical_subscriptions_bytes(
            (FIXTURES / "subscriptions_valid.csv").read_bytes()
        )
        netflix = next(s for s in subs if s.service_name == "Netflix")
        self.assertEqual(Decimal("15.99"), netflix.monthly_equivalent)

    def test_monthly_equivalent_for_annual_billing(self) -> None:
        subs = load_canonical_subscriptions_bytes(
            (FIXTURES / "subscriptions_valid.csv").read_bytes()
        )
        github = next(s for s in subs if s.service_name == "GitHub Pro")
        self.assertEqual(Decimal("48.00"), github.amount)
        # 48 / 12 = 4
        self.assertEqual(Decimal("4.0000"), github.monthly_equivalent)


class SubscriptionServiceTests(unittest.TestCase):
    def _make_service(self, temp_dir: str) -> SubscriptionService:
        return SubscriptionService(
            landing_root=Path(temp_dir) / "landing",
            metadata_repository=RunMetadataRepository(
                Path(temp_dir) / "runs.db"
            ),
        )

    def test_ingest_valid_csv_creates_landed_run(self) -> None:
        with TemporaryDirectory() as temp_dir:
            svc = self._make_service(temp_dir)
            run = svc.ingest_file(FIXTURES / "subscriptions_valid.csv")
            self.assertEqual("landed", run.status.value)
            self.assertEqual("subscriptions", run.dataset_name)

    def test_ingest_invalid_values_creates_rejected_run(self) -> None:
        with TemporaryDirectory() as temp_dir:
            svc = self._make_service(temp_dir)
            run = svc.ingest_file(FIXTURES / "subscriptions_invalid_values.csv")
            self.assertFalse(run.passed)

    def test_get_canonical_subscriptions_returns_rows_for_passed_run(self) -> None:
        with TemporaryDirectory() as temp_dir:
            svc = self._make_service(temp_dir)
            run = svc.ingest_file(FIXTURES / "subscriptions_valid.csv")
            subs = svc.get_canonical_subscriptions(run.run_id)
            self.assertEqual(5, len(subs))
            self.assertIsInstance(subs[0], CanonicalSubscription)

    def test_get_canonical_subscriptions_returns_empty_for_rejected_run(self) -> None:
        with TemporaryDirectory() as temp_dir:
            svc = self._make_service(temp_dir)
            run = svc.ingest_file(FIXTURES / "subscriptions_invalid_values.csv")
            subs = svc.get_canonical_subscriptions(run.run_id)
            self.assertEqual([], subs)


class SubscriptionTransformationTests(unittest.TestCase):
    def _make_rows(self) -> list[dict]:
        return [
            {
                "contract_id": "sub-netflix",
                "service_name": "Netflix",
                "provider": "Netflix Inc.",
                "contract_type": "subscription",
                "billing_cycle": "monthly",
                "amount": "15.99",
                "currency": "EUR",
                "start_date": "2023-01-15",
                "end_date": None,
            },
            {
                "contract_id": "sub-github-pro",
                "service_name": "GitHub Pro",
                "provider": "GitHub Inc.",
                "contract_type": "subscription",
                "billing_cycle": "annual",
                "amount": "48.00",
                "currency": "USD",
                "start_date": "2023-07-01",
                "end_date": None,
            },
            {
                "contract_id": "sub-adobe-cc",
                "service_name": "Adobe CC",
                "provider": "Adobe Systems",
                "contract_type": "subscription",
                "billing_cycle": "annual",
                "amount": "660.00",
                "currency": "EUR",
                "start_date": "2024-01-10",
                "end_date": "2024-12-31",
            },
        ]

    def test_load_subscriptions_inserts_facts(self) -> None:
        svc = TransformationService(DuckDBStore.memory())
        inserted = svc.load_subscriptions(self._make_rows(), run_id="run-sub-001")
        self.assertEqual(3, inserted)

    def test_load_subscriptions_empty_returns_zero(self) -> None:
        svc = TransformationService(DuckDBStore.memory())
        self.assertEqual(0, svc.load_subscriptions([]))

    def test_count_subscriptions(self) -> None:
        svc = TransformationService(DuckDBStore.memory())
        svc.load_subscriptions(self._make_rows(), run_id="run-sub-001")
        self.assertEqual(3, svc.count_subscriptions())
        self.assertEqual(3, svc.count_subscriptions("run-sub-001"))
        self.assertEqual(0, svc.count_subscriptions("run-other"))

    def test_load_subscriptions_upserts_dim_contract(self) -> None:
        svc = TransformationService(DuckDBStore.memory())
        svc.load_subscriptions(self._make_rows(), run_id="run-001")
        contracts = svc.get_current_contracts()
        names = {row["contract_name"] for row in contracts}
        self.assertIn("Netflix", names)
        self.assertIn("GitHub Pro", names)
        self.assertIn("Adobe CC", names)

    def test_refresh_subscription_summary_active_inactive_status(self) -> None:
        svc = TransformationService(DuckDBStore.memory())
        svc.load_subscriptions(self._make_rows(), run_id="run-001")
        count = svc.refresh_subscription_summary()
        self.assertEqual(3, count)

        rows = svc.get_subscription_summary()
        statuses = {r["contract_name"]: r["status"] for r in rows}
        self.assertEqual("active", statuses["Netflix"])
        self.assertEqual("active", statuses["GitHub Pro"])
        # Adobe CC ended 2024-12-31 which is in the past (current date is 2026-03-08)
        self.assertEqual("inactive", statuses["Adobe CC"])

    def test_refresh_subscription_summary_monthly_equivalent(self) -> None:
        svc = TransformationService(DuckDBStore.memory())
        svc.load_subscriptions(self._make_rows(), run_id="run-001")
        svc.refresh_subscription_summary()

        rows = svc.get_subscription_summary()
        github = next(r for r in rows if r["contract_name"] == "GitHub Pro")
        # 48 / 12 = 4
        self.assertEqual(Decimal("4.0000"), Decimal(github["monthly_equivalent"]))

        netflix = next(r for r in rows if r["contract_name"] == "Netflix")
        self.assertEqual(Decimal("15.9900"), Decimal(netflix["monthly_equivalent"]))

    def test_subscription_summary_status_filter(self) -> None:
        svc = TransformationService(DuckDBStore.memory())
        svc.load_subscriptions(self._make_rows(), run_id="run-001")
        svc.refresh_subscription_summary()

        active = svc.get_subscription_summary(status="active")
        self.assertEqual(2, len(active))

        inactive = svc.get_subscription_summary(status="inactive")
        self.assertEqual(1, len(inactive))

    def test_subscription_summary_currency_filter(self) -> None:
        svc = TransformationService(DuckDBStore.memory())
        svc.load_subscriptions(self._make_rows(), run_id="run-001")
        svc.refresh_subscription_summary()

        eur = svc.get_subscription_summary(currency="EUR")
        self.assertEqual(2, len(eur))

        usd = svc.get_subscription_summary(currency="USD")
        self.assertEqual(1, len(usd))


class PromoteSubscriptionRunTests(unittest.TestCase):
    def test_promote_subscription_run_loads_facts(self) -> None:
        with TemporaryDirectory() as temp_dir:
            sub_svc = SubscriptionService(
                landing_root=Path(temp_dir) / "landing",
                metadata_repository=RunMetadataRepository(
                    Path(temp_dir) / "runs.db"
                ),
            )
            ts = TransformationService(DuckDBStore.memory())

            run = sub_svc.ingest_file(FIXTURES / "subscriptions_valid.csv")
            result = promote_subscription_run(
                run.run_id,
                subscription_service=sub_svc,
                transformation_service=ts,
            )

            self.assertFalse(result.skipped)
            self.assertEqual(5, result.facts_loaded)
            self.assertIn("mart_subscription_summary", result.marts_refreshed)
            self.assertIn("mart_upcoming_fixed_costs_30d", result.marts_refreshed)
            self.assertEqual(5, ts.count_subscriptions())

    def test_promote_rejected_run_returns_skipped(self) -> None:
        with TemporaryDirectory() as temp_dir:
            sub_svc = SubscriptionService(
                landing_root=Path(temp_dir) / "landing",
                metadata_repository=RunMetadataRepository(
                    Path(temp_dir) / "runs.db"
                ),
            )
            ts = TransformationService(DuckDBStore.memory())

            run = sub_svc.ingest_file(FIXTURES / "subscriptions_invalid_values.csv")
            result = promote_subscription_run(
                run.run_id,
                subscription_service=sub_svc,
                transformation_service=ts,
            )

            self.assertTrue(result.skipped)
            self.assertEqual(0, result.facts_loaded)
            self.assertEqual(0, ts.count_subscriptions())

    def test_promote_already_promoted_run_returns_skipped(self) -> None:
        with TemporaryDirectory() as temp_dir:
            sub_svc = SubscriptionService(
                landing_root=Path(temp_dir) / "landing",
                metadata_repository=RunMetadataRepository(
                    Path(temp_dir) / "runs.db"
                ),
            )
            ts = TransformationService(DuckDBStore.memory())

            run = sub_svc.ingest_file(FIXTURES / "subscriptions_valid.csv")
            promote_subscription_run(
                run.run_id, subscription_service=sub_svc, transformation_service=ts
            )
            result2 = promote_subscription_run(
                run.run_id, subscription_service=sub_svc, transformation_service=ts
            )

            self.assertTrue(result2.skipped)
            self.assertEqual("run already promoted", result2.skip_reason)
            # Fact count should not have doubled
            self.assertEqual(5, ts.count_subscriptions())


if __name__ == "__main__":
    unittest.main()
