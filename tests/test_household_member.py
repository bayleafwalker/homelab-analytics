"""Tests for dim_household_member schema, seeding, and SCD-2 update path."""
from __future__ import annotations

import unittest
from datetime import date

from packages.pipelines.household_models import (
    CURRENT_DIM_HOUSEHOLD_MEMBER_VIEW,
    DEFAULT_MEMBER_ID,
    DIM_HOUSEHOLD_MEMBER,
    DIM_HOUSEHOLD_MEMBER_TABLE,
)
from packages.pipelines.transformation_household import (
    ensure_household_member_storage,
    get_household_members,
    seed_default_household_member,
    upsert_household_member,
)
from packages.storage.duckdb_store import DuckDBStore


def _store() -> DuckDBStore:
    store = DuckDBStore.memory()
    ensure_household_member_storage(store)
    return store


class DimHouseholdMemberSchemaTests(unittest.TestCase):
    def test_table_name_constant(self) -> None:
        self.assertEqual(DIM_HOUSEHOLD_MEMBER_TABLE, "dim_household_member")

    def test_dimension_definition_natural_key(self) -> None:
        self.assertEqual(DIM_HOUSEHOLD_MEMBER.natural_key_columns, ("member_id",))

    def test_dimension_definition_attribute_columns(self) -> None:
        names = [c.name for c in DIM_HOUSEHOLD_MEMBER.attribute_columns]
        self.assertIn("display_name", names)
        self.assertIn("role", names)
        self.assertIn("active", names)

    def test_current_view_name(self) -> None:
        self.assertEqual(CURRENT_DIM_HOUSEHOLD_MEMBER_VIEW, "rpt_current_dim_household_member")

    def test_ensure_storage_creates_table(self) -> None:
        store = DuckDBStore.memory()
        ensure_household_member_storage(store)
        tables = {row[0] for row in store.connection.execute("SHOW TABLES").fetchall()}
        self.assertIn("dim_household_member", tables)

    def test_ensure_storage_creates_reporting_view(self) -> None:
        store = DuckDBStore.memory()
        ensure_household_member_storage(store)
        # View is queryable without error.
        rows = store.connection.execute(
            "SELECT * FROM rpt_current_dim_household_member"
        ).fetchall()
        self.assertIsInstance(rows, list)


class DimHouseholdMemberSeedTests(unittest.TestCase):
    def test_seed_creates_default_member(self) -> None:
        store = _store()
        seed_default_household_member(store)
        members = get_household_members(store)
        ids = [m["member_id"] for m in members]
        self.assertIn(DEFAULT_MEMBER_ID, ids)

    def test_seed_is_idempotent(self) -> None:
        store = _store()
        seed_default_household_member(store)
        seed_default_household_member(store)
        members = get_household_members(store)
        default_rows = [m for m in members if m["member_id"] == DEFAULT_MEMBER_ID]
        # SCD-2: only the current row should appear in the view.
        self.assertEqual(len(default_rows), 1)

    def test_seed_default_member_has_head_role(self) -> None:
        store = _store()
        seed_default_household_member(store)
        members = get_household_members(store)
        default = next(m for m in members if m["member_id"] == DEFAULT_MEMBER_ID)
        self.assertEqual(default["role"], "head")

    def test_seed_default_member_is_active(self) -> None:
        store = _store()
        seed_default_household_member(store)
        members = get_household_members(store)
        default = next(m for m in members if m["member_id"] == DEFAULT_MEMBER_ID)
        self.assertTrue(default["active"])


class DimHouseholdMemberUpsertTests(unittest.TestCase):
    def test_upsert_inserts_new_member(self) -> None:
        store = _store()
        upsert_household_member(
            store,
            member_id="alice",
            display_name="Alice",
            role="head",
            active=True,
        )
        members = get_household_members(store)
        ids = [m["member_id"] for m in members]
        self.assertIn("alice", ids)

    def test_upsert_multiple_members(self) -> None:
        store = _store()
        for mid, name, role in [
            ("alice", "Alice", "head"),
            ("bob", "Bob", "partner"),
            ("charlie", "Charlie", "dependent"),
        ]:
            upsert_household_member(
                store, member_id=mid, display_name=name, role=role
            )
        members = get_household_members(store)
        ids = {m["member_id"] for m in members}
        self.assertIn("alice", ids)
        self.assertIn("bob", ids)
        self.assertIn("charlie", ids)

    def test_upsert_updates_display_name(self) -> None:
        store = _store()
        upsert_household_member(
            store,
            member_id="alice",
            display_name="Alice Old",
            role="head",
            effective_date=date(2026, 1, 1),
        )
        upsert_household_member(
            store,
            member_id="alice",
            display_name="Alice New",
            role="head",
            effective_date=date(2026, 2, 1),
        )
        members = get_household_members(store)
        alice_rows = [m for m in members if m["member_id"] == "alice"]
        # The reporting view returns only the current row.
        self.assertEqual(len(alice_rows), 1)
        self.assertEqual(alice_rows[0]["display_name"], "Alice New")

    def test_upsert_inactive_member(self) -> None:
        store = _store()
        upsert_household_member(
            store,
            member_id="temp",
            display_name="Temporary",
            role="lodger",
            active=False,
        )
        members = get_household_members(store)
        temp = next((m for m in members if m["member_id"] == "temp"), None)
        self.assertIsNotNone(temp)
        self.assertFalse(temp["active"])


class DimHouseholdMemberGetTests(unittest.TestCase):
    def test_get_household_members_empty_before_seed(self) -> None:
        store = _store()
        members = get_household_members(store)
        self.assertEqual(members, [])

    def test_get_household_members_returns_dicts(self) -> None:
        store = _store()
        seed_default_household_member(store)
        members = get_household_members(store)
        self.assertIsInstance(members, list)
        self.assertIsInstance(members[0], dict)
        self.assertIn("member_id", members[0])
