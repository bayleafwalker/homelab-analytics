"""Tests for category rules, overrides, and enrichment during transaction loading.

Covers:
- Category rule CRUD
- Category override CRUD
- Override > rule > None priority
- Category assignment during load_transactions
- Spend-by-category reflects assigned categories
"""

from __future__ import annotations

import pytest

from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore

LANDING_ROWS = [
    {
        "booked_at": "2026-01-05",
        "account_id": "CHK-001",
        "counterparty_name": "REWE Supermarket",
        "amount": "-42.50",
        "currency": "EUR",
        "description": "Groceries",
    },
    {
        "booked_at": "2026-01-10",
        "account_id": "CHK-001",
        "counterparty_name": "Employer GmbH",
        "amount": "2450.00",
        "currency": "EUR",
        "description": "Salary",
    },
    {
        "booked_at": "2026-01-15",
        "account_id": "CHK-001",
        "counterparty_name": "ALDI Supermarket",
        "amount": "-38.00",
        "currency": "EUR",
        "description": "Groceries",
    },
    {
        "booked_at": "2026-01-20",
        "account_id": "CHK-001",
        "counterparty_name": "Shell Gas Station",
        "amount": "-65.00",
        "currency": "EUR",
        "description": "Fuel",
    },
]


@pytest.fixture()
def svc() -> TransformationService:
    return TransformationService(DuckDBStore.memory())


# ---------------------------------------------------------------------------
# Category rule management
# ---------------------------------------------------------------------------


class TestCategoryRules:
    def test_add_and_list_rules(self, svc: TransformationService) -> None:
        svc.add_category_rule(rule_id="r1", pattern="supermarket", category="groceries")
        svc.add_category_rule(rule_id="r2", pattern="gas station", category="transport")
        rules = svc.list_category_rules()
        assert len(rules) == 2
        patterns = {r["pattern"] for r in rules}
        assert patterns == {"supermarket", "gas station"}

    def test_remove_rule(self, svc: TransformationService) -> None:
        svc.add_category_rule(rule_id="r1", pattern="supermarket", category="groceries")
        svc.remove_category_rule(rule_id="r1")
        assert len(svc.list_category_rules()) == 0

    def test_rule_priority_order(self, svc: TransformationService) -> None:
        svc.add_category_rule(
            rule_id="r1", pattern="rewe", category="rewe-specific", priority=10
        )
        svc.add_category_rule(
            rule_id="r2", pattern="supermarket", category="groceries", priority=5
        )
        rules = svc.list_category_rules()
        # Higher priority first
        assert rules[0]["category"] == "rewe-specific"
        assert rules[1]["category"] == "groceries"


# ---------------------------------------------------------------------------
# Category override management
# ---------------------------------------------------------------------------


class TestCategoryOverrides:
    def test_set_and_list_overrides(self, svc: TransformationService) -> None:
        svc.set_category_override(counterparty_name="Employer GmbH", category="income")
        overrides = svc.list_category_overrides()
        assert len(overrides) == 1
        assert overrides[0]["counterparty_name"] == "Employer GmbH"
        assert overrides[0]["category"] == "income"

    def test_remove_override(self, svc: TransformationService) -> None:
        svc.set_category_override(counterparty_name="Employer GmbH", category="income")
        svc.remove_category_override(counterparty_name="Employer GmbH")
        assert len(svc.list_category_overrides()) == 0

    def test_override_replaces_existing(self, svc: TransformationService) -> None:
        svc.set_category_override(counterparty_name="X", category="old")
        svc.set_category_override(counterparty_name="X", category="new")
        overrides = svc.list_category_overrides()
        assert len(overrides) == 1
        assert overrides[0]["category"] == "new"


# ---------------------------------------------------------------------------
# Category resolution priority: override > rule > None
# ---------------------------------------------------------------------------


class TestCategoryResolution:
    def test_rule_assigns_category_during_load(self, svc: TransformationService) -> None:
        svc.add_category_rule(rule_id="r1", pattern="supermarket", category="groceries")
        svc.load_transactions(LANDING_ROWS, run_id="run-001")

        counterparties = svc.get_current_counterparties()
        by_name = {c["counterparty_name"]: c for c in counterparties}
        assert by_name["REWE Supermarket"]["category"] == "groceries"
        assert by_name["ALDI Supermarket"]["category"] == "groceries"

    def test_no_rule_leaves_category_none(self, svc: TransformationService) -> None:
        svc.load_transactions(LANDING_ROWS, run_id="run-001")

        counterparties = svc.get_current_counterparties()
        by_name = {c["counterparty_name"]: c for c in counterparties}
        assert by_name["Shell Gas Station"]["category"] is None

    def test_override_beats_rule(self, svc: TransformationService) -> None:
        svc.add_category_rule(rule_id="r1", pattern="supermarket", category="groceries")
        svc.set_category_override(
            counterparty_name="REWE Supermarket", category="preferred-grocer"
        )
        svc.load_transactions(LANDING_ROWS, run_id="run-001")

        counterparties = svc.get_current_counterparties()
        by_name = {c["counterparty_name"]: c for c in counterparties}
        # Override wins for REWE
        assert by_name["REWE Supermarket"]["category"] == "preferred-grocer"
        # Rule still applies to ALDI
        assert by_name["ALDI Supermarket"]["category"] == "groceries"

    def test_higher_priority_rule_wins(self, svc: TransformationService) -> None:
        svc.add_category_rule(
            rule_id="r1", pattern="rewe", category="rewe-specific", priority=10
        )
        svc.add_category_rule(
            rule_id="r2", pattern="supermarket", category="groceries", priority=5
        )
        svc.load_transactions(LANDING_ROWS, run_id="run-001")

        counterparties = svc.get_current_counterparties()
        by_name = {c["counterparty_name"]: c for c in counterparties}
        # REWE matches both rules — higher priority wins
        assert by_name["REWE Supermarket"]["category"] == "rewe-specific"
        # ALDI only matches "supermarket"
        assert by_name["ALDI Supermarket"]["category"] == "groceries"


# ---------------------------------------------------------------------------
# Integration: category flows into spend_by_category_monthly
# ---------------------------------------------------------------------------


class TestCategoryInSpendReport:
    def test_spend_by_category_reflects_assigned_categories(
        self, svc: TransformationService
    ) -> None:
        svc.add_category_rule(rule_id="r1", pattern="supermarket", category="groceries")
        svc.add_category_rule(rule_id="r2", pattern="gas station", category="transport")
        svc.load_transactions(LANDING_ROWS, run_id="run-001")
        svc.refresh_spend_by_category_monthly()

        rows = svc.get_spend_by_category_monthly()
        categories = {r["counterparty_name"]: r["category"] for r in rows}
        assert categories["REWE Supermarket"] == "groceries"
        assert categories["ALDI Supermarket"] == "groceries"
        assert categories["Shell Gas Station"] == "transport"

    def test_category_filter_works(self, svc: TransformationService) -> None:
        svc.add_category_rule(rule_id="r1", pattern="supermarket", category="groceries")
        svc.add_category_rule(rule_id="r2", pattern="gas station", category="transport")
        svc.load_transactions(LANDING_ROWS, run_id="run-001")
        svc.refresh_spend_by_category_monthly()

        groceries = svc.get_spend_by_category_monthly(category="groceries")
        assert len(groceries) == 2
        assert all(r["category"] == "groceries" for r in groceries)
