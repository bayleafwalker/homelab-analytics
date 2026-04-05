"""Dimension and fact definitions for balance snapshots."""

from __future__ import annotations

FACT_BALANCE_SNAPSHOT_TABLE = "fact_balance_snapshot"

FACT_BALANCE_SNAPSHOT_COLUMNS: list[tuple[str, str]] = [
    ("snapshot_id", "VARCHAR PRIMARY KEY"),
    ("snapshot_date", "DATE NOT NULL"),
    ("balance_kind", "VARCHAR NOT NULL"),
    ("entity_id", "VARCHAR NOT NULL"),
    ("entity_label", "VARCHAR"),
    ("balance_amount", "DECIMAL(18,4) NOT NULL"),
    ("currency", "VARCHAR NOT NULL"),
    ("run_id", "VARCHAR"),
]
