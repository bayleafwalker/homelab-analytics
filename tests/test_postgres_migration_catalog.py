"""Static integrity checks over the Postgres control-plane migrations.

A fresh Postgres control plane applies ``migrations/postgres`` in filename
order before anything else runs, so a publication row that references a
transformation package no earlier migration seeded takes the api down at
startup with a foreign-key violation. These checks catch that in the repo
rather than in a cluster.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.docs]

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = ROOT / "migrations" / "postgres"

_INSERT_BLOCK = re.compile(
    r"INSERT INTO (?P<table>\w+)\s*\((?P<columns>[^)]*)\)\s*VALUES(?P<values>.*?);",
    re.DOTALL | re.IGNORECASE,
)


def _ordered_migrations() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def _insert_blocks(sql: str, table: str) -> list[tuple[list[str], str]]:
    blocks = []
    for match in _INSERT_BLOCK.finditer(sql):
        if match.group("table").lower() != table:
            continue
        columns = [column.strip() for column in match.group("columns").split(",")]
        blocks.append((columns, match.group("values")))
    return blocks


def _first_column_values(sql: str, table: str) -> list[str]:
    values: list[str] = []
    for _columns, block in _insert_blocks(sql, table):
        values.extend(re.findall(r"\(\s*'([^']+)'", block))
    return values


def _package_references(sql: str) -> list[str]:
    references: list[str] = []
    for columns, block in _insert_blocks(sql, "publication_definitions"):
        try:
            index = columns.index("transformation_package_id")
        except ValueError:
            continue
        # NOW() would otherwise break the parenthesis-delimited row split.
        rows = re.findall(r"\(([^()]*)\)", block.replace("NOW()", "NOW"))
        for row in rows:
            fields = re.findall(r"'([^']*)'|(NULL|FALSE|TRUE|NOW)", row)
            flattened = [first or second for first, second in fields]
            if len(flattened) > index:
                references.append(flattened[index])
    return references


def test_publication_definitions_only_reference_already_seeded_packages() -> None:
    seeded: set[str] = set()

    for migration in _ordered_migrations():
        sql = migration.read_text()
        seeded.update(_first_column_values(sql, "transformation_packages"))
        missing = sorted(
            reference for reference in _package_references(sql) if reference not in seeded
        )
        assert not missing, (
            f"{migration.name} inserts publication_definitions rows referencing "
            f"transformation packages that no migration up to and including it "
            f"seeds: {missing}"
        )


def test_asset_register_package_is_seeded() -> None:
    seeded: set[str] = set()
    for migration in _ordered_migrations():
        seeded.update(_first_column_values(migration.read_text(), "transformation_packages"))

    assert "builtin_asset_register" in seeded
