"""Reporting mart reads dispatch through domain-owned readers (sprint item #2814)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import packages.pipelines.reporting_service as reporting_service_module
from packages.domains.finance.pipelines.transaction_models import MART_MONTHLY_CASHFLOW_TABLE
from packages.domains.finance.pipelines.transformation_transactions import get_monthly_cashflow
from packages.pipelines.mart_read_registry import (
    MartReadRegistry,
    SchemaEnsuringReader,
    get_default_mart_read_registry,
    read_warehouse_mart,
)
from packages.pipelines.reporting_service import ReportingAccessMode, ReportingService
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore

ROOT = Path(__file__).resolve().parents[1]


def _reporting_mart_reads() -> set[str]:
    """Relation constants ReportingService reads through ``self._read_mart``."""
    source = (ROOT / "packages" / "pipelines" / "reporting_service.py").read_text()
    constants = re.findall(r"self\._read_mart\(\s*([A-Z_][A-Z0-9_]*)", source)
    assert constants, "ReportingService no longer reads through the mart read registry"
    return {getattr(reporting_service_module, constant) for constant in constants}


def test_default_registry_serves_every_reporting_service_mart_read() -> None:
    registry = get_default_mart_read_registry()
    assert _reporting_mart_reads() <= set(registry.relation_names())


def test_every_mart_reader_is_owned_by_a_domain_pack() -> None:
    registry = get_default_mart_read_registry()
    for name in registry.relation_names():
        reader = registry.reader(name)
        if isinstance(reader, SchemaEnsuringReader):
            reader = reader.reader
        owner = reader.__module__
        assert owner.startswith("packages.domains."), (name, owner)


def test_registry_rejects_conflicting_readers_and_unknown_relations() -> None:
    registry = MartReadRegistry()
    registry.register("mart_x", get_monthly_cashflow)
    registry.register("mart_x", get_monthly_cashflow)  # same reader is idempotent
    with pytest.raises(ValueError, match="already registered"):
        registry.register("mart_x", lambda store: [])
    with pytest.raises(KeyError, match="Unknown mart read: mart_nope"):
        registry.reader("mart_nope")
    registry.register("mart_y", SchemaEnsuringReader(get_monthly_cashflow))
    assert registry.requires_write("mart_y")
    assert not registry.requires_write("mart_x")


def test_reporting_service_reads_the_warehouse_through_an_injected_registry() -> None:
    registry = MartReadRegistry()
    seen: list[dict[str, object]] = []

    def _reader(store: DuckDBStore, **filters: object) -> list[dict[str, object]]:
        seen.append(filters)
        return [{"booking_month": "2026-01"}]

    registry.register(MART_MONTHLY_CASHFLOW_TABLE, _reader)
    reporting = ReportingService(
        TransformationService(DuckDBStore.memory()),
        access_mode=ReportingAccessMode.WAREHOUSE,
        mart_read_registry=registry,
    )

    assert reporting.get_monthly_cashflow(from_month="2026-01") == [
        {"booking_month": "2026-01"}
    ]
    assert seen == [{"from_month": "2026-01", "to_month": None}]


def test_read_warehouse_mart_reads_a_plain_service_store() -> None:
    service = TransformationService(DuckDBStore.memory())
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
        run_id="run-mart-001",
    )
    service.refresh_publications([MART_MONTHLY_CASHFLOW_TABLE])

    rows = read_warehouse_mart(service, MART_MONTHLY_CASHFLOW_TABLE, from_month="2026-01")
    assert rows == get_monthly_cashflow(service.store, from_month="2026-01")
    assert [row["booking_month"] for row in rows] == ["2026-01"]
