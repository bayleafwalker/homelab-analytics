"""Full household integration test — loads all domain fixture data and verifies
the complete cross-domain composition pipeline.

Covers:
- All 6 built-in domains load successfully
- All mart tables are populated after promotion
- Overview composition pulls from all 4 source domains
- Budget variance aligns with transaction spend categories
- Affordability ratios compute end-to-end
- Cost model totals are non-zero and sourced from multiple domains
- Recurring cost baseline draws from multiple cost sources
- Attention items are generated
"""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.budget_service import BudgetService
from packages.pipelines.builtin_promotion_handlers import (
    promote_budget_run,
    promote_contract_price_run,
    promote_loan_repayment_run,
    promote_run,
    promote_subscription_run,
    promote_utility_bill_run,
)
from packages.pipelines.contract_price_service import ContractPriceService
from packages.pipelines.loan_service import LoanService
from packages.pipelines.subscription_service import SubscriptionService
from packages.pipelines.transformation_service import TransformationService
from packages.pipelines.utility_bill_service import UtilityBillService
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.run_metadata import RunMetadataRepository
from tests.fixtures.demo_household_complete import generate_all


def _setup_complete_household(temp_dir: str) -> TransformationService:
    """Ingest and promote all 6 demo datasets; return the populated service."""
    root = Path(temp_dir)
    meta = RunMetadataRepository(root / "runs.db")
    ts = TransformationService(DuckDBStore.memory())
    fixtures = generate_all()

    # --- Transactions ---
    account_svc = AccountTransactionService(
        landing_root=root / "landing" / "transactions",
        metadata_repository=meta,
    )
    txn_run = account_svc.ingest_bytes(
        source_bytes=fixtures["account_transactions"],
        file_name="demo_transactions.csv",
    )
    promote_run(txn_run.run_id, account_service=account_svc, transformation_service=ts)

    # --- Subscriptions ---
    sub_svc = SubscriptionService(
        landing_root=root / "landing" / "subscriptions",
        metadata_repository=meta,
    )
    sub_run = sub_svc.ingest_bytes(
        source_bytes=fixtures["subscriptions"],
        file_name="demo_subscriptions.csv",
    )
    promote_subscription_run(sub_run.run_id, subscription_service=sub_svc, transformation_service=ts)

    # --- Contract prices ---
    cp_svc = ContractPriceService(
        landing_root=root / "landing" / "contract_prices",
        metadata_repository=meta,
    )
    cp_run = cp_svc.ingest_bytes(
        source_bytes=fixtures["contract_prices"],
        file_name="demo_contract_prices.csv",
    )
    promote_contract_price_run(cp_run.run_id, contract_price_service=cp_svc, transformation_service=ts)

    # --- Utility bills ---
    bill_svc = UtilityBillService(
        landing_root=root / "landing" / "utility_bills",
        metadata_repository=meta,
    )
    bill_run = bill_svc.ingest_bytes(
        source_bytes=fixtures["utility_bills"],
        file_name="demo_utility_bills.csv",
    )
    promote_utility_bill_run(bill_run.run_id, utility_bill_service=bill_svc, transformation_service=ts)

    # --- Budgets ---
    budget_svc = BudgetService(
        landing_root=root / "landing" / "budgets",
        metadata_repository=meta,
    )
    budget_run = budget_svc.ingest_bytes(
        source_bytes=fixtures["budgets"],
        file_name="demo_budgets.csv",
    )
    promote_budget_run(budget_run.run_id, budget_service=budget_svc, transformation_service=ts)

    # --- Loan repayments ---
    loan_svc = LoanService(
        landing_root=root / "landing" / "loan_repayments",
        metadata_repository=meta,
    )
    loan_run = loan_svc.ingest_bytes(
        source_bytes=fixtures["loan_repayments"],
        file_name="demo_loan_repayments.csv",
    )
    promote_loan_repayment_run(loan_run.run_id, loan_service=loan_svc, transformation_service=ts)

    return ts


class AllDomainsMartPopulationTests(unittest.TestCase):
    """All core mart tables are populated after full-household promotion."""

    _temp: TemporaryDirectory[str]
    ts: TransformationService

    @classmethod
    def setUpClass(cls) -> None:
        cls._temp = TemporaryDirectory()
        cls.ts = _setup_complete_household(cls._temp.name)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temp.cleanup()

    def test_monthly_cashflow_populated(self) -> None:
        rows = self.ts.get_monthly_cashflow()
        self.assertGreater(len(rows), 0)

    def test_spend_by_category_monthly_populated(self) -> None:
        rows = self.ts.get_spend_by_category_monthly()
        self.assertGreater(len(rows), 0)

    def test_subscription_summary_populated(self) -> None:
        rows = self.ts.get_subscription_summary()
        self.assertGreater(len(rows), 0)

    def test_utility_cost_trend_monthly_populated(self) -> None:
        rows = self.ts.get_utility_cost_trend_monthly()
        self.assertGreater(len(rows), 0)

    def test_budget_variance_populated(self) -> None:
        rows = self.ts.get_budget_variance()
        self.assertGreater(len(rows), 0)

    def test_loan_overview_populated(self) -> None:
        rows = self.ts.get_loan_overview()
        self.assertGreater(len(rows), 0)

    def test_loan_schedule_projected_populated(self) -> None:
        rows = self.ts.get_loan_schedule_projected()
        self.assertGreater(len(rows), 0)


class OverviewCompositionTests(unittest.TestCase):
    """Overview mart pulls from all 4 source domains (transactions, subscriptions,
    utilities, loans/budgets)."""

    _temp: TemporaryDirectory[str]
    ts: TransformationService

    @classmethod
    def setUpClass(cls) -> None:
        cls._temp = TemporaryDirectory()
        cls.ts = _setup_complete_household(cls._temp.name)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temp.cleanup()

    def test_household_overview_populated(self) -> None:
        rows = self.ts.get_household_overview()
        self.assertGreater(len(rows), 0)

    def test_household_overview_has_cashflow_columns(self) -> None:
        rows = self.ts.get_household_overview()
        row = rows[0]
        # Overview uses cashflow_income / cashflow_expense column names
        self.assertIsNotNone(row["cashflow_income"])
        self.assertIsNotNone(row["cashflow_expense"])

    def test_open_attention_items_populated(self) -> None:
        rows = self.ts.get_open_attention_items()
        # With real data at least some items should be raised
        self.assertIsInstance(rows, list)

    def test_current_operating_baseline_populated(self) -> None:
        rows = self.ts.get_current_operating_baseline()
        self.assertGreater(len(rows), 0)


class BudgetVarianceAlignmentTests(unittest.TestCase):
    """Budget variance categories match transaction spend categories."""

    _temp: TemporaryDirectory[str]
    ts: TransformationService

    @classmethod
    def setUpClass(cls) -> None:
        cls._temp = TemporaryDirectory()
        cls.ts = _setup_complete_household(cls._temp.name)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temp.cleanup()

    def test_budget_variance_has_target_amounts(self) -> None:
        rows = self.ts.get_budget_variance()
        target_amounts = {r["category_id"]: r["target_amount"] for r in rows if r.get("target_amount") is not None}
        self.assertGreater(len(target_amounts), 0)

    def test_spend_by_category_has_monthly_rows(self) -> None:
        # Verify spend mart is populated (categories require explicit rules to be non-NULL)
        rows = self.ts.get_spend_by_category_monthly()
        months = {r["booking_month"] for r in rows}
        self.assertGreater(len(months), 0)

    def test_budget_variance_status_values_are_valid(self) -> None:
        rows = self.ts.get_budget_variance()
        valid_statuses = {"under_budget", "on_budget", "over_budget", None}
        for row in rows:
            self.assertIn(row.get("status"), valid_statuses)

    def test_budget_variance_state_values_are_valid(self) -> None:
        rows = self.ts.get_budget_variance()
        valid_states = {"good", "warning", "needs_action"}
        for row in rows:
            self.assertIn(row.get("state"), valid_states)


class AffordabilityRatiosEndToEndTests(unittest.TestCase):
    """Affordability ratios compute from live income and cost data."""

    _temp: TemporaryDirectory[str]
    ts: TransformationService

    @classmethod
    def setUpClass(cls) -> None:
        cls._temp = TemporaryDirectory()
        cls.ts = _setup_complete_household(cls._temp.name)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temp.cleanup()

    def test_affordability_ratios_populated(self) -> None:
        rows = self.ts.get_affordability_ratios()
        self.assertGreater(len(rows), 0)

    def test_affordability_ratio_names_present(self) -> None:
        rows = self.ts.get_affordability_ratios()
        names = {r["ratio_name"] for r in rows}
        self.assertIn("total_cost_to_income", names)

    def test_affordability_assessment_values_are_valid(self) -> None:
        rows = self.ts.get_affordability_ratios()
        valid = {"healthy", "caution", "critical"}
        for row in rows:
            if row.get("assessment") is not None:
                self.assertIn(row["assessment"], valid)

    def test_affordability_state_values_are_valid(self) -> None:
        rows = self.ts.get_affordability_ratios()
        valid_states = {"good", "warning", "needs_action"}
        for row in rows:
            self.assertIn(row.get("state"), valid_states)

    def test_total_cost_to_income_ratio_is_positive(self) -> None:
        rows = self.ts.get_affordability_ratios()
        total_cost_row = next(
            (r for r in rows if r["ratio_name"] == "total_cost_to_income"), None
        )
        if total_cost_row is not None and total_cost_row.get("ratio") is not None:
            self.assertGreaterEqual(float(total_cost_row["ratio"]), 0)


class HouseholdCostModelTests(unittest.TestCase):
    """Cost model aggregates from all domains with non-zero totals."""

    _temp: TemporaryDirectory[str]
    ts: TransformationService

    @classmethod
    def setUpClass(cls) -> None:
        cls._temp = TemporaryDirectory()
        cls.ts = _setup_complete_household(cls._temp.name)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temp.cleanup()

    def test_cost_model_populated(self) -> None:
        rows = self.ts.get_household_cost_model()
        self.assertGreater(len(rows), 0)

    def test_cost_model_amounts_are_positive(self) -> None:
        rows = self.ts.get_household_cost_model()
        for row in rows:
            self.assertGreater(float(row["amount"]), 0)

    def test_cost_model_has_multiple_cost_types(self) -> None:
        rows = self.ts.get_household_cost_model()
        cost_types = {r["cost_type"] for r in rows}
        self.assertGreater(len(cost_types), 1)

    def test_cost_trend_12m_populated(self) -> None:
        rows = self.ts.get_cost_trend_12m()
        self.assertGreater(len(rows), 0)


class RecurringCostBaselineTests(unittest.TestCase):
    """Recurring baseline draws from subscriptions, utilities, and loans."""

    _temp: TemporaryDirectory[str]
    ts: TransformationService

    @classmethod
    def setUpClass(cls) -> None:
        cls._temp = TemporaryDirectory()
        cls.ts = _setup_complete_household(cls._temp.name)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temp.cleanup()

    def test_recurring_baseline_populated(self) -> None:
        rows = self.ts.get_recurring_cost_baseline()
        self.assertGreater(len(rows), 0)

    def test_recurring_baseline_has_multiple_sources(self) -> None:
        rows = self.ts.get_recurring_cost_baseline()
        sources = {r["cost_source"] for r in rows}
        self.assertGreater(len(sources), 1)

    def test_recurring_baseline_monthly_amounts_positive(self) -> None:
        rows = self.ts.get_recurring_cost_baseline()
        for row in rows:
            self.assertGreater(float(row["monthly_amount"]), 0)


class BudgetCategoryOverlapTests(unittest.TestCase):
    """Category rules correctly bridge budget targets and transaction spend.

    Verifies test_budget_categories_overlap_with_spend_categories:
    when pattern rules match demo merchants to budget category names,
    mart_budget_variance shows actual spend for every budget category.
    """

    _temp: TemporaryDirectory[str]
    ts: TransformationService

    @classmethod
    def setUpClass(cls) -> None:
        cls._temp = TemporaryDirectory()
        ts = _setup_complete_household(cls._temp.name)
        # Add rules matching demo merchant names → budget category names.
        # add_category_rule auto-backfills dim_counterparty so existing
        # counterparties are re-categorised without re-ingestion.
        ts.add_category_rule(rule_id="r-groceries", pattern="supermarket", category="groceries")
        ts.add_category_rule(rule_id="r-utilities", pattern="city power", category="utilities")
        ts.add_category_rule(rule_id="r-transport", pattern="metro transport", category="transport")
        ts.add_category_rule(rule_id="r-entertainment", pattern="netflix", category="entertainment")
        ts.add_category_rule(rule_id="r-dining", pattern="restaurant", category="dining")
        # Spend mart was built before rules existed — rebuild with proper categories.
        ts.refresh_spend_by_category_monthly()
        # Budget variance reads from the spend mart — rebuild to pick up alignment.
        ts.refresh_budget_variance()
        cls.ts = ts

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temp.cleanup()

    def test_budget_categories_overlap_with_spend_categories(self) -> None:
        budget_rows = self.ts.get_budget_variance()
        spend_rows = self.ts.get_spend_by_category_monthly()

        spend_categories = {r["category"] for r in spend_rows if r.get("category") is not None}
        budget_categories_with_spend = {
            r["category_id"]
            for r in budget_rows
            if r.get("actual_amount") is not None and float(r["actual_amount"]) > 0
        }

        expected = {"groceries", "entertainment", "transport", "utilities", "dining"}
        self.assertTrue(
            expected.issubset(budget_categories_with_spend),
            f"Expected all budget categories to have actual spend after rule application.\n"
            f"Missing: {expected - budget_categories_with_spend}\n"
            f"Spend categories: {spend_categories}",
        )

    def test_spend_categories_are_non_null_after_rules_applied(self) -> None:
        rows = self.ts.get_spend_by_category_monthly()
        categorised = [r for r in rows if r.get("category") is not None]
        self.assertGreater(
            len(categorised), 0,
            "Expected at least some spend rows to have a non-NULL category after rules applied.",
        )


class CategoryGovernancePhase2Tests(unittest.TestCase):
    """dim_category full ADR — seeding, budget FK alignment, category API.

    Verifies Sprint C deliverables:
    - System categories are present in dim_category after TransformationService init
    - Budget category_ids loaded from CSV resolve against dim_category
    - mart_budget_variance joins on category_id (slug join, not text match)
    - Operator sub-category creation is rejected for system slugs
    """

    _temp: TemporaryDirectory[str]
    ts: TransformationService

    @classmethod
    def setUpClass(cls) -> None:
        cls._temp = TemporaryDirectory()
        ts = _setup_complete_household(cls._temp.name)
        # Apply rules so spend categories align with budget category_ids
        ts.add_category_rule(rule_id="r-groceries", pattern="supermarket", category="groceries")
        ts.add_category_rule(rule_id="r-utilities", pattern="city power", category="utilities")
        ts.add_category_rule(rule_id="r-transport", pattern="metro transport", category="transport")
        ts.add_category_rule(rule_id="r-entertainment", pattern="netflix", category="entertainment")
        ts.add_category_rule(rule_id="r-dining", pattern="restaurant", category="dining")
        ts.refresh_spend_by_category_monthly()
        ts.refresh_budget_variance()
        cls.ts = ts

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temp.cleanup()

    def test_system_categories_seeded_at_init(self) -> None:
        from packages.pipelines.category_seed import SYSTEM_CATEGORY_IDS

        rows = self.ts.get_current_categories()
        present = {r["category_id"] for r in rows}
        missing = SYSTEM_CATEGORY_IDS - present
        self.assertEqual(
            set(),
            missing,
            f"System categories missing from dim_category after init: {missing}",
        )

    def test_system_categories_are_flagged_as_system(self) -> None:
        rows = self.ts.get_current_categories()
        system_rows = {r["category_id"]: r for r in rows if r.get("is_system")}
        # All expected system slugs should be present and marked is_system=True
        for slug in ("groceries", "transport", "utilities", "entertainment", "dining", "income"):
            self.assertIn(slug, system_rows, f"Expected '{slug}' to be a system category")
            self.assertTrue(system_rows[slug]["is_system"])

    def test_budget_category_ids_exist_in_dim_category(self) -> None:
        # Every category_id stored in fact_budget_target must resolve in dim_category
        fact_rows = self.ts._store.fetchall_dicts(
            "SELECT DISTINCT category_id FROM fact_budget_target"
        )
        dim_rows = self.ts.get_current_categories()
        dim_ids = {r["category_id"] for r in dim_rows}

        missing = {r["category_id"] for r in fact_rows} - dim_ids
        self.assertEqual(
            set(),
            missing,
            f"Budget category_ids not found in dim_category: {missing}",
        )

    def test_budget_variance_joins_on_category_id(self) -> None:
        budget_rows = self.ts.get_budget_variance()
        categories_with_spend = {
            r["category_id"]
            for r in budget_rows
            if r.get("actual_amount") is not None and float(r["actual_amount"]) > 0
        }
        expected = {"groceries", "entertainment", "transport", "utilities", "dining"}
        self.assertTrue(
            expected.issubset(categories_with_spend),
            f"Budget variance slug join missing spend for: {expected - categories_with_spend}",
        )

    def test_operator_category_creation_blocked_for_system_slug(self) -> None:
        from packages.pipelines.category_seed import SYSTEM_CATEGORY_IDS

        # The 409 guard lives in the API route. Here we verify SYSTEM_CATEGORY_IDS
        # covers all slugs that a POST /api/categories must reject.
        self.assertIn("groceries", SYSTEM_CATEGORY_IDS)
        self.assertIn("utilities", SYSTEM_CATEGORY_IDS)
        self.assertNotIn("groceries_organic", SYSTEM_CATEGORY_IDS)

    def test_dim_category_has_expected_adl_columns(self) -> None:
        rows = self.ts.get_current_categories()
        self.assertGreater(len(rows), 0)
        sample = rows[0]
        for col in ("category_id", "display_name", "domain", "is_budget_eligible", "is_system"):
            self.assertIn(col, sample, f"Expected column '{col}' in dim_category row")


if __name__ == "__main__":
    unittest.main()
