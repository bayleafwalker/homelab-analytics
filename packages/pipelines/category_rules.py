"""Deterministic category assignment for counterparties.

Categories are assigned via two mechanisms in priority order:
1. Manual overrides — explicit (counterparty_name → category) mappings
2. Pattern rules — substring-match rules (pattern → category)

No ML or fuzzy matching. Rules are reproducible and auditable.
"""

from __future__ import annotations

from typing import Any

from packages.storage.duckdb_store import DuckDBStore

# ---------------------------------------------------------------------------
# Storage schema
# ---------------------------------------------------------------------------

CATEGORY_RULE_TABLE = "category_rule"
CATEGORY_RULE_COLUMNS: list[tuple[str, str]] = [
    ("rule_id", "VARCHAR PRIMARY KEY"),
    ("pattern", "VARCHAR NOT NULL"),        # substring match (case-insensitive)
    ("category", "VARCHAR NOT NULL"),       # category to assign
    ("priority", "INTEGER NOT NULL"),       # higher = matched first
]

CATEGORY_OVERRIDE_TABLE = "category_override"
CATEGORY_OVERRIDE_COLUMNS: list[tuple[str, str]] = [
    ("counterparty_name", "VARCHAR PRIMARY KEY"),
    ("category", "VARCHAR NOT NULL"),
]


def ensure_category_storage(store: DuckDBStore) -> None:
    store.ensure_table(CATEGORY_RULE_TABLE, CATEGORY_RULE_COLUMNS)
    store.ensure_table(CATEGORY_OVERRIDE_TABLE, CATEGORY_OVERRIDE_COLUMNS)


# ---------------------------------------------------------------------------
# Rule management
# ---------------------------------------------------------------------------


def add_category_rule(
    store: DuckDBStore,
    *,
    rule_id: str,
    pattern: str,
    category: str,
    priority: int = 0,
) -> None:
    store.execute(
        f"""
        INSERT OR REPLACE INTO {CATEGORY_RULE_TABLE}
            (rule_id, pattern, category, priority)
        VALUES (?, ?, ?, ?)
        """,
        [rule_id, pattern, category, priority],
    )


def remove_category_rule(store: DuckDBStore, *, rule_id: str) -> None:
    store.execute(
        f"DELETE FROM {CATEGORY_RULE_TABLE} WHERE rule_id = ?",
        [rule_id],
    )


def list_category_rules(store: DuckDBStore) -> list[dict[str, Any]]:
    return store.fetchall_dicts(
        f"SELECT * FROM {CATEGORY_RULE_TABLE} ORDER BY priority DESC, pattern"
    )


# ---------------------------------------------------------------------------
# Override management
# ---------------------------------------------------------------------------


def set_category_override(
    store: DuckDBStore,
    *,
    counterparty_name: str,
    category: str,
) -> None:
    store.execute(
        f"""
        INSERT OR REPLACE INTO {CATEGORY_OVERRIDE_TABLE}
            (counterparty_name, category)
        VALUES (?, ?)
        """,
        [counterparty_name, category],
    )


def remove_category_override(
    store: DuckDBStore,
    *,
    counterparty_name: str,
) -> None:
    store.execute(
        f"DELETE FROM {CATEGORY_OVERRIDE_TABLE} WHERE counterparty_name = ?",
        [counterparty_name],
    )


def list_category_overrides(store: DuckDBStore) -> list[dict[str, Any]]:
    return store.fetchall_dicts(
        f"SELECT * FROM {CATEGORY_OVERRIDE_TABLE} ORDER BY counterparty_name"
    )


# ---------------------------------------------------------------------------
# Category resolution
# ---------------------------------------------------------------------------


def resolve_category(
    store: DuckDBStore,
    counterparty_name: str,
) -> str | None:
    """Resolve category for a counterparty: override > rule > None."""
    # 1. Check manual override
    overrides = store.fetchall_dicts(
        f"SELECT category FROM {CATEGORY_OVERRIDE_TABLE} WHERE counterparty_name = ?",
        [counterparty_name],
    )
    if overrides:
        return overrides[0]["category"]

    # 2. Check pattern rules (highest priority first)
    rules = store.fetchall_dicts(
        f"SELECT category FROM {CATEGORY_RULE_TABLE} ORDER BY priority DESC, pattern"
    )
    name_lower = counterparty_name.lower()
    for rule in rules:
        if rule["pattern"].lower() in name_lower:
            return rule["category"]

    return None


def backfill_counterparty_categories(store: DuckDBStore) -> int:
    """Re-evaluate and update category for all current dim_counterparty rows.

    Called after any rule or override change so that historical spend data
    reflects the new categorisation without requiring a re-ingestion.
    Returns the number of counterparty rows updated.
    """
    rows = store.fetchall_dicts(
        "SELECT DISTINCT counterparty_name FROM dim_counterparty WHERE valid_to IS NULL"
    )
    if not rows:
        return 0
    names = [r["counterparty_name"] for r in rows]
    resolved = resolve_categories_bulk(store, names)
    for name, category in resolved.items():
        store.execute(
            "UPDATE dim_counterparty SET category = ? WHERE counterparty_name = ? AND valid_to IS NULL",
            [category, name],
        )
    return len(resolved)


def resolve_categories_bulk(
    store: DuckDBStore,
    counterparty_names: list[str],
) -> dict[str, str | None]:
    """Resolve categories for multiple counterparties at once."""
    # Load all overrides and rules once
    overrides = {
        row["counterparty_name"]: row["category"]
        for row in store.fetchall_dicts(
            f"SELECT counterparty_name, category FROM {CATEGORY_OVERRIDE_TABLE}"
        )
    }
    rules = store.fetchall_dicts(
        f"SELECT pattern, category FROM {CATEGORY_RULE_TABLE} ORDER BY priority DESC, pattern"
    )

    result: dict[str, str | None] = {}
    for name in counterparty_names:
        if name in overrides:
            result[name] = overrides[name]
            continue
        name_lower = name.lower()
        matched = None
        for rule in rules:
            if rule["pattern"].lower() in name_lower:
                matched = rule["category"]
                break
        result[name] = matched

    return result
