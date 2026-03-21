"""System category seeding for the dim_category dimension.

System categories are immutable canonical slugs seeded at init time.
Operators may add sub-categories (is_system=False) but cannot rename
or delete system rows.

Seeding is idempotent — safe to call on every startup via the
TransformationService._ensure_storage() path.
"""

from __future__ import annotations

from packages.pipelines.subscription_models import DIM_CATEGORY
from packages.storage.duckdb_store import DuckDBStore

# ---------------------------------------------------------------------------
# Canonical system category definitions
# ---------------------------------------------------------------------------

SYSTEM_CATEGORIES: list[dict] = [
    # Shared top-level
    {
        "category_id": "housing",
        "display_name": "Housing",
        "parent_id": None,
        "domain": "shared",
        "is_budget_eligible": True,
        "is_system": True,
    },
    # Finance top-level
    {
        "category_id": "groceries",
        "display_name": "Groceries",
        "parent_id": None,
        "domain": "finance",
        "is_budget_eligible": True,
        "is_system": True,
    },
    {
        "category_id": "transport",
        "display_name": "Transport",
        "parent_id": None,
        "domain": "finance",
        "is_budget_eligible": True,
        "is_system": True,
    },
    {
        "category_id": "subscriptions",
        "display_name": "Subscriptions",
        "parent_id": None,
        "domain": "finance",
        "is_budget_eligible": True,
        "is_system": True,
    },
    {
        "category_id": "entertainment",
        "display_name": "Entertainment",
        "parent_id": None,
        "domain": "finance",
        "is_budget_eligible": True,
        "is_system": True,
    },
    {
        "category_id": "dining",
        "display_name": "Dining",
        "parent_id": None,
        "domain": "finance",
        "is_budget_eligible": True,
        "is_system": True,
    },
    {
        "category_id": "income",
        "display_name": "Income",
        "parent_id": None,
        "domain": "finance",
        "is_budget_eligible": False,
        "is_system": True,
    },
    # Utilities top-level + sub-categories
    {
        "category_id": "utilities",
        "display_name": "Utilities",
        "parent_id": None,
        "domain": "utilities",
        "is_budget_eligible": True,
        "is_system": True,
    },
    {
        "category_id": "utilities_electricity",
        "display_name": "Electricity",
        "parent_id": "utilities",
        "domain": "utilities",
        "is_budget_eligible": True,
        "is_system": True,
    },
    {
        "category_id": "utilities_gas",
        "display_name": "Gas",
        "parent_id": "utilities",
        "domain": "utilities",
        "is_budget_eligible": True,
        "is_system": True,
    },
    # Homelab top-level
    {
        "category_id": "homelab",
        "display_name": "Homelab",
        "parent_id": None,
        "domain": "homelab",
        "is_budget_eligible": True,
        "is_system": True,
    },
]

SYSTEM_CATEGORY_IDS: frozenset[str] = frozenset(
    c["category_id"] for c in SYSTEM_CATEGORIES
)


def seed_system_categories(store: DuckDBStore) -> int:
    """Upsert all system categories into dim_category.

    Idempotent — rows with unchanged attributes produce no new SCD2 version.
    Returns the number of rows upserted (new versions written).
    """
    return store.upsert_dimension_rows(DIM_CATEGORY, SYSTEM_CATEGORIES)
