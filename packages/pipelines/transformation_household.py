"""Transformation helpers for the household-member dimension.

Provides:
- ``ensure_household_member_storage`` — create/migrate table + reporting view
- ``seed_default_household_member``   — upsert the default 'household' member
- ``upsert_household_member``         — add or update one member
- ``get_household_members``           — return all current members

The default member (``member_id='household'``) is seeded automatically so
that single-person deployments work without any manual configuration.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from packages.pipelines.household_models import (
    CURRENT_DIM_HOUSEHOLD_MEMBER_VIEW,
    DEFAULT_MEMBER_DISPLAY_NAME,
    DEFAULT_MEMBER_ID,
    DEFAULT_MEMBER_ROLE,
    DIM_HOUSEHOLD_MEMBER,
)
from packages.storage.duckdb_store import DuckDBStore


def ensure_household_member_storage(store: DuckDBStore) -> None:
    """Create the dim_household_member table and reporting view if absent."""
    store.ensure_dimension(DIM_HOUSEHOLD_MEMBER)
    store.ensure_current_dimension_view(DIM_HOUSEHOLD_MEMBER, CURRENT_DIM_HOUSEHOLD_MEMBER_VIEW)


def seed_default_household_member(
    store: DuckDBStore,
    *,
    effective_date: date | None = None,
) -> None:
    """Upsert the default 'household' member if it does not already exist.

    Called during ``ensure_household_member_storage`` so that a fresh database
    always has at least one member and existing attribution queries do not break.
    """
    existing = store.query_current(DIM_HOUSEHOLD_MEMBER)
    if any(row.get("member_id") == DEFAULT_MEMBER_ID for row in existing):
        return
    store.upsert_dimension_rows(
        DIM_HOUSEHOLD_MEMBER,
        [
            {
                "member_id": DEFAULT_MEMBER_ID,
                "display_name": DEFAULT_MEMBER_DISPLAY_NAME,
                "role": DEFAULT_MEMBER_ROLE,
                "active": True,
            }
        ],
        effective_date=effective_date,
        source_system="seed",
    )


def upsert_household_member(
    store: DuckDBStore,
    *,
    member_id: str,
    display_name: str,
    role: str,
    active: bool = True,
    effective_date: date | None = None,
) -> None:
    """Insert or update a household member using SCD-2 semantics.

    The underlying ``upsert_dimension_rows`` call handles closing the prior
    version row and inserting a new current row when any attribute changes.
    """
    store.upsert_dimension_rows(
        DIM_HOUSEHOLD_MEMBER,
        [
            {
                "member_id": member_id,
                "display_name": display_name,
                "role": role,
                "active": active,
            }
        ],
        effective_date=effective_date,
        source_system="operator",
    )


def get_household_members(store: DuckDBStore) -> list[dict[str, Any]]:
    """Return all current household members."""
    return store.query_current(DIM_HOUSEHOLD_MEMBER)
