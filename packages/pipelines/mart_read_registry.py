"""Mart read dispatch: domain packs own the warehouse readers behind reporting.

``ReportingService`` serves a mart from the warehouse (warehouse access mode,
or the prefer-published fallback) through this registry instead of holding a
``TransformationService`` getter per mart. Each pack registers its reporting
reads as ``relation name -> reader(store, **filters)``; the built-in
composition lives in ``packages.pipelines.household_mart_reads``.

Reads are leased: :func:`read_warehouse_mart` runs a reader on one warehouse
handle via :func:`packages.pipelines.reporting_snapshots.run_on_warehouse`, so
under ``warehouse_session`` API reads stay on short-lived read-only handles. A
reader that issues DDL before reading (``ensure_*_storage``) is registered as
:class:`SchemaEnsuringReader` and gets a read-write handle instead.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from packages.storage.duckdb_store import DuckDBStore

MartReader = Callable[..., list[dict[str, Any]]]


@dataclass(frozen=True)
class SchemaEnsuringReader:
    """A reader that creates its storage before reading; it needs a read-write handle."""

    reader: MartReader

    def __call__(self, store: DuckDBStore, **filters: Any) -> list[dict[str, Any]]:
        return self.reader(store, **filters)


class MartReadRegistry:
    def __init__(self) -> None:
        self._readers: dict[str, MartReader] = {}

    def register(self, relation_name: str, reader: MartReader) -> None:
        existing = self._readers.get(relation_name)
        if existing is not None and existing != reader:
            raise ValueError(f"Mart reader already registered: {relation_name}")
        self._readers[relation_name] = reader

    def reader(self, relation_name: str) -> MartReader:
        try:
            return self._readers[relation_name]
        except KeyError as exc:
            raise KeyError(f"Unknown mart read: {relation_name}") from exc

    def read(
        self, store: DuckDBStore, relation_name: str, **filters: Any
    ) -> list[dict[str, Any]]:
        return self.reader(relation_name)(store, **filters)

    def requires_write(self, relation_name: str) -> bool:
        return isinstance(self.reader(relation_name), SchemaEnsuringReader)

    def relation_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._readers))


_DEFAULT_MART_READ_REGISTRY: MartReadRegistry | None = None


def get_default_mart_read_registry() -> MartReadRegistry:
    global _DEFAULT_MART_READ_REGISTRY
    if _DEFAULT_MART_READ_REGISTRY is None:
        from packages.pipelines.household_mart_reads import register_builtin_mart_readers

        registry = MartReadRegistry()
        register_builtin_mart_readers(registry)
        _DEFAULT_MART_READ_REGISTRY = registry
    return _DEFAULT_MART_READ_REGISTRY


def read_warehouse_mart(
    transformation_service: Any,
    relation_name: str,
    *,
    registry: MartReadRegistry | None = None,
    **filters: Any,
) -> list[dict[str, Any]]:
    """Read ``relation_name`` from the warehouse on one handle of the right mode.

    ``transformation_service`` is a ``TransformationService`` or its
    ``warehouse_session`` stand-in; only its ``store`` (or session leases) is used.
    """
    from packages.pipelines.reporting_snapshots import run_on_warehouse

    resolved = registry or get_default_mart_read_registry()
    reader = resolved.reader(relation_name)
    return run_on_warehouse(
        transformation_service,
        f"mart_read.{relation_name}",
        lambda store: reader(store, **filters),
        write=resolved.requires_write(relation_name),
    )
