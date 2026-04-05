"""Dimension and fact definitions for the household-member domain.

Provides:
- ``DIM_HOUSEHOLD_MEMBER``  — SCD Type 1 member dimension
- ``DIM_HOUSEHOLD_MEMBER_TABLE`` — canonical table name constant
- ``CURRENT_DIM_HOUSEHOLD_MEMBER_VIEW`` — reporting-layer view name

Stage 1 carryover: dim_household_member is the last canonical dimension
named in the roadmap that was not yet implemented.  It enables attribution
of transactions, assets, loans, and subscriptions to individual household
members.
"""

from __future__ import annotations

from packages.storage.duckdb_store import DimensionColumn, DimensionDefinition

# ---------------------------------------------------------------------------
# Dimension definitions
# ---------------------------------------------------------------------------

DIM_HOUSEHOLD_MEMBER = DimensionDefinition(
    table_name="dim_household_member",
    natural_key_columns=("member_id",),
    attribute_columns=(
        DimensionColumn("display_name", "VARCHAR"),
        DimensionColumn("role", "VARCHAR"),
        DimensionColumn("active", "BOOLEAN"),
    ),
)

DIM_HOUSEHOLD_MEMBER_TABLE = "dim_household_member"

CURRENT_DIM_HOUSEHOLD_MEMBER_VIEW = "rpt_current_dim_household_member"

# ---------------------------------------------------------------------------
# Role vocabulary
# ---------------------------------------------------------------------------

MEMBER_ROLES = ("head", "partner", "dependent", "lodger")

DEFAULT_MEMBER_ID = "household"
DEFAULT_MEMBER_DISPLAY_NAME = "Household"
DEFAULT_MEMBER_ROLE = "head"
