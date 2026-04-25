from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast

from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.domains.finance.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.run_metadata import RunMetadataRepository
from tests.test_homelab_domain import _service_rows, _workload_rows

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
                "audit_id": "audit-001",
                "input_run_id": input_run_id or "run-001",
                "fact_rows": 2,
                "started_at": "2026-03-10T10:00:00+00:00",
                "completed_at": "2026-03-10T10:00:01+00:00",
                "duration_ms": 1000,
                "accounts_upserted": 1,
                "counterparties_upserted": 1,
            }
        ]

    def publish_publications(self, publication_keys: list[str]):
        self.publications.append(list(publication_keys))
        return publication_keys

    def publish_auxiliary_relations(self, relation_names: list[str]):
        self.auxiliary_relations.append(list(relation_names))
        return relation_names


class NewReportingEndpointTests(unittest.TestCase):
    """Tests for the dedicated reporting endpoints added for all 18 publications."""

    def _make_app_with_data(self, temp_dir: str) -> TestClient:
        service = AccountTransactionService(
            landing_root=Path(temp_dir) / "landing",
            metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
        )
        ts = TransformationService(DuckDBStore.memory())

        # Load transaction data
        ts.load_transactions(
            [
                {
                    "booked_at": "2026-01-05",
                    "account_id": "CHK-001",
                    "counterparty_name": "Shop",
                    "amount": "-50.00",
                    "currency": "EUR",
                    "description": "Groceries",
                },
                {
                    "booked_at": "2026-01-10",
                    "account_id": "CHK-001",
                    "counterparty_name": "Employer",
                    "amount": "2500.00",
                    "currency": "EUR",
                    "description": "Salary",
                },
            ],
            run_id="run-001",
        )
        ts.refresh_monthly_cashflow()
        ts.refresh_spend_by_category_monthly()
        ts.refresh_recent_large_transactions()
        ts.refresh_account_balance_trend()
        ts.refresh_transaction_anomalies_current()

        # Load subscription data
        ts.load_subscriptions(
            [
                {
                    "contract_id": "sub-netflix",
                    "service_name": "Netflix",
                    "provider": "Netflix Inc.",
                    "contract_type": "subscription",
                    "billing_cycle": "monthly",
                    "amount": "15.99",
                    "currency": "EUR",
                    "start_date": "2025-01-15",
                    "end_date": None,
                }
            ],
            run_id="run-002",
        )
        ts.refresh_subscription_summary()
        ts.refresh_upcoming_fixed_costs_30d()
        ts.load_budget_targets(
            [
                {
                    "budget_id": "bgt-001",
                    "budget_name": "Monthly Budget",
                    "category_id": "groceries",
                    "period_type": "monthly",
                    "period_label": "2026-01",
                    "target_amount": "400.00",
                    "currency": "EUR",
                }
            ],
            run_id="run-003",
        )
        ts.refresh_budget_variance()
        ts.refresh_budget_envelope_drift()

        # Load homelab data for the operator value-loop surface.
        ts.load_service_health(_service_rows(), run_id="run-hl-services")
        ts.refresh_service_health_current()
        ts.load_workload_sensors(_workload_rows(), run_id="run-hl-workloads")
        ts.refresh_workload_cost_7d()
        ts.refresh_homelab_roi()

        # Refresh overview
        ts.refresh_household_overview()
        ts.refresh_open_attention_items()
        ts.refresh_recent_significant_changes()
        ts.refresh_current_operating_baseline()

        app = create_app(service, transformation_service=ts)
        return TestClient(app)

    def test_spend_by_category_monthly_endpoint(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client = self._make_app_with_data(temp_dir)
            response = client.get("/reports/spend-by-category-monthly")
        self.assertEqual(200, response.status_code)
        self.assertIn("rows", response.json())

    def test_recent_large_transactions_endpoint(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client = self._make_app_with_data(temp_dir)
            response = client.get("/reports/recent-large-transactions")
        self.assertEqual(200, response.status_code)
        self.assertIn("rows", response.json())

    def test_account_balance_trend_endpoint(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client = self._make_app_with_data(temp_dir)
            response = client.get("/reports/account-balance-trend")
        self.assertEqual(200, response.status_code)
        self.assertIn("rows", response.json())

    def test_transaction_anomalies_endpoint(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client = self._make_app_with_data(temp_dir)
            response = client.get("/reports/transaction-anomalies")
        self.assertEqual(200, response.status_code)
        self.assertIn("rows", response.json())

    def test_upcoming_fixed_costs_endpoint(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client = self._make_app_with_data(temp_dir)
            response = client.get("/reports/upcoming-fixed-costs")
        self.assertEqual(200, response.status_code)
        self.assertIn("rows", response.json())

    def test_budget_envelopes_endpoint(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client = self._make_app_with_data(temp_dir)
            response = client.get("/reports/budget-envelopes")
        self.assertEqual(200, response.status_code)
        rows = response.json()["rows"]
        self.assertEqual(1, len(rows))
        self.assertEqual("under_target", rows[0]["drift_state"])
        self.assertEqual("good", rows[0]["state"])

    def test_budget_variance_endpoint_exposes_normalized_state(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client = self._make_app_with_data(temp_dir)
            response = client.get("/reports/budget-variance")
        self.assertEqual(200, response.status_code)
        rows = response.json()["rows"]
        self.assertEqual(1, len(rows))
        self.assertEqual("under_budget", rows[0]["status"])
        self.assertEqual("good", rows[0]["state"])

    def test_household_overview_endpoint(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client = self._make_app_with_data(temp_dir)
            response = client.get("/reports/household-overview")
        self.assertEqual(200, response.status_code)
        rows = response.json()["rows"]
        self.assertEqual(1, len(rows))

    def test_homelab_roi_endpoint(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client = self._make_app_with_data(temp_dir)
            response = client.get("/reports/homelab-roi")
        self.assertEqual(200, response.status_code)
        rows = response.json()["rows"]
        self.assertEqual(1, len(rows))
        self.assertIn(rows[0]["roi_state"], {"good", "warning", "needs_action", "empty"})

    def test_attention_items_endpoint(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client = self._make_app_with_data(temp_dir)
            response = client.get("/reports/attention-items")
        self.assertEqual(200, response.status_code)
        self.assertIn("rows", response.json())

    def test_recent_changes_endpoint(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client = self._make_app_with_data(temp_dir)
            response = client.get("/reports/recent-changes")
        self.assertEqual(200, response.status_code)
        self.assertIn("rows", response.json())

    def test_homelab_services_endpoint(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client = self._make_app_with_data(temp_dir)
            response = client.get("/api/homelab/services")
        self.assertEqual(200, response.status_code)
        rows = response.json()["rows"]
        self.assertGreater(len(rows), 0)
        self.assertIn("state", rows[0])

    def test_homelab_workloads_endpoint(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client = self._make_app_with_data(temp_dir)
            response = client.get("/api/homelab/workloads")
        self.assertEqual(200, response.status_code)
        rows = response.json()["rows"]
        self.assertGreater(len(rows), 0)
        self.assertIn("est_monthly_cost", rows[0])

    def test_operating_baseline_endpoint(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client = self._make_app_with_data(temp_dir)
            response = client.get("/reports/operating-baseline")
        self.assertEqual(200, response.status_code)
        rows = response.json()["rows"]
        self.assertEqual(4, len(rows))

    def test_endpoint_returns_404_without_transformation_service(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = AccountTransactionService(
                landing_root=Path(temp_dir) / "landing",
                metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
            )
            client = TestClient(create_app(service))
            for path in (
                "/reports/spend-by-category-monthly",
                "/reports/recent-large-transactions",
                "/reports/account-balance-trend",
                "/reports/transaction-anomalies",
                "/reports/upcoming-fixed-costs",
                "/reports/budget-envelopes",
                "/reports/household-overview",
                "/reports/attention-items",
                "/reports/recent-changes",
                "/reports/operating-baseline",
                "/api/homelab/services",
                "/api/homelab/workloads",
            ):
                response = client.get(path)
                self.assertEqual(
                    404,
                    response.status_code,
                    f"{path} should return 404 without transformation service",
                )


class CategoryApiTests(unittest.TestCase):
    """Tests for the category rules and overrides API endpoints."""

    def _make_app(self, temp_dir: str) -> TestClient:
        service = AccountTransactionService(
            landing_root=Path(temp_dir) / "landing",
            metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
        )
        ts = TransformationService(DuckDBStore.memory())
        app = create_app(service, transformation_service=ts)
        return TestClient(app)

    def test_create_and_list_category_rules(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client = self._make_app(temp_dir)
            response = client.post(
                "/categories/rules",
                params={"rule_id": "r1", "pattern": "supermarket", "category": "groceries"},
            )
            self.assertEqual(201, response.status_code)

            list_response = client.get("/categories/rules")
            self.assertEqual(200, list_response.status_code)
            payload = list_response.json()
            self.assertNotIn("rules", payload)
            rules = payload["rows"]
            self.assertEqual(1, len(rules))
            self.assertEqual("supermarket", rules[0]["pattern"])

    def test_delete_category_rule(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client = self._make_app(temp_dir)
            client.post(
                "/categories/rules",
                params={"rule_id": "r1", "pattern": "x", "category": "y"},
            )
            delete_response = client.delete("/categories/rules/r1")
            self.assertEqual(200, delete_response.status_code)

            rules_payload = client.get("/categories/rules").json()
            self.assertNotIn("rules", rules_payload)
            rules = rules_payload["rows"]
            self.assertEqual(0, len(rules))

    def test_set_and_list_category_overrides(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client = self._make_app(temp_dir)
            response = client.put(
                "/categories/overrides/Employer",
                params={"category": "income"},
            )
            self.assertEqual(200, response.status_code)

            list_response = client.get("/categories/overrides")
            self.assertEqual(200, list_response.status_code)
            payload = list_response.json()
            self.assertNotIn("overrides", payload)
            overrides = payload["rows"]
            self.assertEqual(1, len(overrides))
            self.assertEqual("income", overrides[0]["category"])

    def test_delete_category_override(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client = self._make_app(temp_dir)
            client.put("/categories/overrides/X", params={"category": "y"})
            delete_response = client.delete("/categories/overrides/X")
            self.assertEqual(200, delete_response.status_code)

            overrides_payload = client.get("/categories/overrides").json()
            self.assertNotIn("overrides", overrides_payload)
            overrides = overrides_payload["rows"]
            self.assertEqual(0, len(overrides))


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
        self.assertNotIn("audit", response.json())
        self.assertEqual(
            [
                {
                    "audit_id": "audit-001",
                    "input_run_id": "run-123",
                    "fact_rows": 2,
                    "started_at": "2026-03-10T10:00:00+00:00",
                    "completed_at": "2026-03-10T10:00:01+00:00",
                    "duration_ms": 1000,
                    "accounts_upserted": 1,
                    "counterparties_upserted": 1,
                }
            ],
            response.json()["rows"],
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
                    "mart_spend_by_category_monthly",
                    "mart_recent_large_transactions",
                    "mart_account_balance_trend",
                    "mart_transaction_anomalies_current",
                ]
            ],
            reporting_service.publications,
        )
        self.assertEqual(
            [
                ["transformation_audit"],
                [
                    "mart_current_operating_baseline",
                    "mart_household_overview",
                    "mart_open_attention_items",
                    "mart_recent_significant_changes",
                ],
            ],
            reporting_service.auxiliary_relations,
        )
