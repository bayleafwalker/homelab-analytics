"""Tests for dim_counterparty.category_id governance (Sprint Q)."""
from __future__ import annotations

import unittest
from datetime import date

from packages.domains.finance.pipelines.transformation_transactions import (
    populate_counterparty_category_ids,
)
from packages.storage.duckdb_store import DimensionColumn, DimensionDefinition, DuckDBStore

# Minimal counterparty dimension for test isolation.
_DIM_COUNTERPARTY = DimensionDefinition(
    table_name="dim_counterparty",
    natural_key_columns=("counterparty_name",),
    attribute_columns=(
        DimensionColumn("category", "VARCHAR"),
        DimensionColumn("category_id", "VARCHAR"),
    ),
)

_DIM_CATEGORY = DimensionDefinition(
    table_name="dim_category",
    natural_key_columns=("category_id",),
    attribute_columns=(
        DimensionColumn("display_name", "VARCHAR"),
    ),
)


def _setup_store() -> DuckDBStore:
    store = DuckDBStore.memory()
    store.ensure_dimension(_DIM_COUNTERPARTY)
    store.ensure_dimension(_DIM_CATEGORY)
    return store


def _seed_category(store: DuckDBStore, category_id: str, display_name: str) -> None:
    store.upsert_dimension_rows(
        _DIM_CATEGORY,
        [{"category_id": category_id, "display_name": display_name}],
        effective_date=date(2026, 1, 1),
        source_system="test",
    )


def _seed_counterparty(
    store: DuckDBStore,
    counterparty_name: str,
    category: str | None = None,
    category_id: str | None = None,
) -> None:
    row: dict = {"counterparty_name": counterparty_name, "category": category, "category_id": category_id}
    store.upsert_dimension_rows(
        _DIM_COUNTERPARTY,
        [row],
        effective_date=date(2026, 1, 1),
        source_system="test",
    )


class CounterpartyCategoryIdTests(unittest.TestCase):
    def test_category_id_column_exists_on_dimension(self) -> None:
        names = [c.name for c in _DIM_COUNTERPARTY.attribute_columns]
        self.assertIn("category_id", names)

    def test_backfill_resolves_category_id_by_display_name(self) -> None:
        store = _setup_store()
        _seed_category(store, "groceries", "Groceries")
        _seed_counterparty(store, "Lidl", category="Groceries")

        updated = populate_counterparty_category_ids(store)

        rows = store.query_current(_DIM_COUNTERPARTY)
        lidl = next(r for r in rows if r["counterparty_name"] == "Lidl")
        self.assertEqual(lidl["category_id"], "groceries")
        self.assertEqual(updated, 1)

    def test_backfill_does_not_overwrite_existing_category_id(self) -> None:
        store = _setup_store()
        _seed_category(store, "groceries", "Groceries")
        # Pre-populate category_id; backfill should skip it.
        _seed_counterparty(store, "Lidl", category="Groceries", category_id="already_set")

        updated = populate_counterparty_category_ids(store)

        rows = store.query_current(_DIM_COUNTERPARTY)
        lidl = next(r for r in rows if r["counterparty_name"] == "Lidl")
        self.assertEqual(lidl["category_id"], "already_set")
        self.assertEqual(updated, 0)

    def test_backfill_leaves_unmatched_counterparty_null(self) -> None:
        store = _setup_store()
        _seed_category(store, "groceries", "Groceries")
        _seed_counterparty(store, "Unknown Vendor", category="Unknown")

        populate_counterparty_category_ids(store)

        rows = store.query_current(_DIM_COUNTERPARTY)
        vendor = next(r for r in rows if r["counterparty_name"] == "Unknown Vendor")
        self.assertIsNone(vendor["category_id"])

    def test_backfill_handles_null_category_bridge(self) -> None:
        store = _setup_store()
        _seed_counterparty(store, "No Category Vendor", category=None)

        count = populate_counterparty_category_ids(store)

        self.assertEqual(count, 0)

    def test_backfill_is_idempotent(self) -> None:
        store = _setup_store()
        _seed_category(store, "groceries", "Groceries")
        _seed_counterparty(store, "Lidl", category="Groceries")

        first = populate_counterparty_category_ids(store)
        second = populate_counterparty_category_ids(store)

        self.assertEqual(first, 1)
        self.assertEqual(second, 0)

    def test_free_text_category_column_retained(self) -> None:
        store = _setup_store()
        _seed_category(store, "groceries", "Groceries")
        _seed_counterparty(store, "Lidl", category="Groceries")
        populate_counterparty_category_ids(store)

        rows = store.query_current(_DIM_COUNTERPARTY)
        lidl = next(r for r in rows if r["counterparty_name"] == "Lidl")
        # Free-text bridge must still be present.
        self.assertEqual(lidl["category"], "Groceries")
        # FK also resolved.
        self.assertEqual(lidl["category_id"], "groceries")
