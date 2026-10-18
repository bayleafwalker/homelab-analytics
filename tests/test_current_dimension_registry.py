"""Current-dimension reads dispatch through domain-owned readers (sprint #512 #1881)."""

from __future__ import annotations

import pytest

from packages.pipelines.current_dimension_registry import (
    CurrentDimensionRegistry,
    CurrentViewReader,
    get_default_current_dimension_registry,
)
from packages.pipelines.household_reporting import CURRENT_DIMENSION_RELATIONS
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore


def _owner_module(reader: object) -> str:
    if isinstance(reader, CurrentViewReader):
        # View readers are declared in the pack's current_dimensions module.
        return "declared"
    return reader.__module__  # type: ignore[attr-defined]


def test_default_registry_covers_every_reporting_current_dimension() -> None:
    registry = get_default_current_dimension_registry()

    # dim_household_member is platform-owned (transformation_household) and was
    # never served by get_current_dimension_rows; behaviour is unchanged.
    assert set(registry.dimension_names()) == set(CURRENT_DIMENSION_RELATIONS) - {
        "dim_household_member"
    }
    for name in registry.dimension_names():
        owner = _owner_module(registry.reader(name))
        assert owner == "declared" or owner.startswith("packages.domains."), (name, owner)


def test_facade_reads_current_dimensions_through_the_registry() -> None:
    store = DuckDBStore.memory()
    service = TransformationService(store)
    service.load_transactions(
        [
            {
                "booked_at": "2026-01-03T08:00:00+00:00",
                "account_id": "checking",
                "counterparty_name": "Employer",
                "amount": "3000.00",
                "currency": "EUR",
                "description": "salary",
            }
        ],
        run_id="run-dim-001",
    )

    rows = service.get_current_dimension_rows("dim_account")
    assert [row["account_id"] for row in rows] == ["checking"]
    assert service.get_current_dimension_rows("dim_category")  # seeded system categories
    with pytest.raises(KeyError, match="Unknown current dimension: dim_nope"):
        service.get_current_dimension_rows("dim_nope")


def test_registry_rejects_conflicting_readers_and_accepts_injection() -> None:
    registry = CurrentDimensionRegistry()
    reader = CurrentViewReader("v", "k")
    registry.register("dim_x", reader)
    registry.register("dim_x", CurrentViewReader("v", "k"))  # equal reader is idempotent
    with pytest.raises(ValueError, match="already registered"):
        registry.register("dim_x", CurrentViewReader("w", "k"))

    registry.register("dim_custom", lambda store: [{"id": 1}])
    service = TransformationService(DuckDBStore.memory(), current_dimension_registry=registry)
    assert service.get_current_dimension_rows("dim_custom") == [{"id": 1}]
