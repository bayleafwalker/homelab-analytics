"""Current-dimension read dispatch: domain packs own their current-dimension readers.

``TransformationService.get_current_dimension_rows`` dispatches here instead of
holding one getter per dimension. The registry is domain-agnostic; the
built-in composition lives in ``packages.pipelines.household_current_dimensions``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from packages.storage.duckdb_store import DuckDBStore

CurrentDimensionReader = Callable[[DuckDBStore], list[dict[str, Any]]]


@dataclass(frozen=True)
class CurrentViewReader:
    """Reads every row of a current-dimension view in a stable order."""

    view_name: str
    order_by: str

    def __call__(self, store: DuckDBStore) -> list[dict[str, Any]]:
        return store.fetchall_dicts(f"SELECT * FROM {self.view_name} ORDER BY {self.order_by}")


class CurrentDimensionRegistry:
    def __init__(self) -> None:
        self._readers: dict[str, CurrentDimensionReader] = {}

    def register(self, dimension_name: str, reader: CurrentDimensionReader) -> None:
        existing = self._readers.get(dimension_name)
        if existing is not None and existing != reader:
            raise ValueError(f"Current dimension reader already registered: {dimension_name}")
        self._readers[dimension_name] = reader

    def read(self, store: DuckDBStore, dimension_name: str) -> list[dict[str, Any]]:
        try:
            reader = self._readers[dimension_name]
        except KeyError as exc:
            raise KeyError(f"Unknown current dimension: {dimension_name}") from exc
        return reader(store)

    def reader(self, dimension_name: str) -> CurrentDimensionReader:
        return self._readers[dimension_name]

    def dimension_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._readers))


_DEFAULT_CURRENT_DIMENSION_REGISTRY: CurrentDimensionRegistry | None = None


def get_default_current_dimension_registry() -> CurrentDimensionRegistry:
    global _DEFAULT_CURRENT_DIMENSION_REGISTRY
    if _DEFAULT_CURRENT_DIMENSION_REGISTRY is None:
        from packages.pipelines.household_current_dimensions import (
            register_builtin_current_dimension_readers,
        )

        registry = CurrentDimensionRegistry()
        register_builtin_current_dimension_readers(registry)
        _DEFAULT_CURRENT_DIMENSION_REGISTRY = registry
    return _DEFAULT_CURRENT_DIMENSION_REGISTRY
