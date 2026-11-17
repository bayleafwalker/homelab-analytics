"""Regression tests for currency-separated reporting.

Covers the behaviours the upgrade and the read paths must keep: legacy
snapshots surface as unavailable (never valid-empty, never given a currency),
usage-only rows differ from an observed zero bill, legacy-shaped relations are
refused with a 503, the migration chain and the runtime registry agree, the
upgrade command reports completion only after a full single-invocation
upgrade, and each direct consumer states amounts per currency.
"""

from __future__ import annotations

import io
import json
import shutil
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient

from apps.api.app import create_app
from apps.api.ha_startup import _compute_electricity_cost_forecast_today
from apps.api.routes.assistant_routes import _build_finance_answer, _build_utilities_answer
from apps.worker.main import main
from packages.application.use_cases.morning_brief import (
    PublicationInput,
    compose_morning_brief,
)
from packages.application.use_cases.morning_brief_sections import MONTHLY_CASHFLOW_KEY
from packages.domains.finance.pipelines.account_transaction_service import (
    AccountTransactionService,
)
from packages.domains.utilities.pipelines.transformation_utilities import (
    get_utility_cost_summary,
    refresh_utility_cost_summary,
)
from packages.pipelines import reporting_upgrade
from packages.pipelines.reporting_currency import (
    CURRENCY_COLUMN_RELATIONS,
    UPGRADE_COMMAND,
    StaleReportingSchemaError,
    assert_currency_current,
)
from packages.pipelines.reporting_service import ReportingAccessMode, ReportingService
from packages.pipelines.reporting_snapshots import (
    SNAPSHOT_COLUMNS,
    SNAPSHOT_TABLE,
    PublicationSnapshot,
    is_legacy_denomination_snapshot,
)
from packages.pipelines.reporting_upgrade import (
    _REBUILD_ONLY_RELATIONS,
    _RELATIONS,
    EXIT_COMPLETE,
    EXIT_FAILED,
    EXIT_REFUSED,
    MIGRATION_VERSION,
    _duck_states,
    _duck_table_exists,
    run_upgrade,
)
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.migration_runner import apply_pending_duckdb_migrations
from packages.storage.postgres_reporting import PostgresReportingStore
from packages.storage.run_metadata import RunMetadataRepository
from tests.postgres_test_support import running_postgres_container
from tests.test_currency_consumer_regressions import _bill
from tests.test_currency_consumer_regressions import _usage as _meter_usage
from tests.test_energy_contract_decision import _assess, _usage
from tests.test_morning_brief import _confidence, _inputs, _publications, _section
from tests.test_reporting_upgrade import _columns, _legacy_warehouse, _settings

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations" / "duckdb"


# ---------------------------------------------------------------------------
# Migration chain and runtime registry
# ---------------------------------------------------------------------------


def _chain_before_0020(target: Path) -> Path:
    target.mkdir(parents=True, exist_ok=True)
    for migration in sorted(MIGRATIONS.glob("*.sql")):
        if migration.stem < MIGRATION_VERSION:
            shutil.copy(migration, target / migration.name)
    return target


def test_migration_chain_matches_the_runtime_registry(tmp_path: Path) -> None:
    store = DuckDBStore.memory()
    apply_pending_duckdb_migrations(store.connection, _chain_before_0020(tmp_path / "old"))
    before = _duck_states(store)
    # Before 0020 the altered relations are legacy; the rebuild-only relations
    # already carry their current columns from the initial schema.
    assert set(before.values()) == {"legacy", "current"}, before
    for relation in _RELATIONS:
        assert before[relation.name] == "legacy", relation.name
    for relation in _REBUILD_ONLY_RELATIONS:
        assert before[relation.name] == "current", relation.name

    applied = apply_pending_duckdb_migrations(store.connection, MIGRATIONS)
    assert applied == [MIGRATION_VERSION]
    after = _duck_states(store)
    assert set(after.values()) == {"current"}, after
    # The migration only appends; the rebuilt tables keep their column order.
    for relation in _RELATIONS:
        described = [row[0] for row in store.fetchall(f"DESCRIBE {relation.name}")]
        assert described == [name for name, _ in relation.columns], relation.name


def test_registry_and_stale_guard_cover_the_same_relations() -> None:
    altered = {r.name for r in _RELATIONS if r.added == "currency"}
    assert altered == set(CURRENCY_COLUMN_RELATIONS)
    assert _RELATIONS[-1].name == SNAPSHOT_TABLE
    assert _RELATIONS[-1].added == "contract_version"
    assert SNAPSHOT_COLUMNS[-1][0] == "contract_version"


# ---------------------------------------------------------------------------
# Upgrade command: first invocation, partial failure, installed-store shapes
# ---------------------------------------------------------------------------


def test_first_invocation_reports_full_completion(tmp_path: Path) -> None:
    warehouse = tmp_path / "warehouse.duckdb"
    _legacy_warehouse(warehouse)
    stdout, stderr = io.StringIO(), io.StringIO()

    code = main(
        ["upgrade-reporting"],
        stdout=stdout,
        stderr=stderr,
        settings=_settings(tmp_path, warehouse),
    )

    receipt = json.loads(stdout.getvalue())
    assert code == 0, (stderr.getvalue(), receipt)
    # stdout is exactly one completion JSON object; the worker start log is on
    # stderr for this machine-readable command (never mixed into stdout).
    assert "worker command starting" in stderr.getvalue()
    assert receipt["status"] == "complete" and receipt["phase"] == "done"
    assert receipt["facts"]["before"] == receipt["facts"]["after"]
    assert "mart_monthly_cashflow" in receipt["rebuilt_marts"]
    assert receipt["next_step"] is None
    assert not (tmp_path / "metadata" / "runs.db").exists()
    # Reads work immediately: no second invocation is needed.
    for relation in _RELATIONS:
        assert _columns(warehouse, relation.name) == [name for name, _ in relation.columns]


def test_partial_failure_is_incomplete_with_recovery_then_rerun_completes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    warehouse = tmp_path / "warehouse.duckdb"
    _legacy_warehouse(warehouse)
    original = reporting_upgrade._verify_duckdb

    def boom(_store: Any) -> None:
        raise RuntimeError("simulated failure after the rebuild")

    monkeypatch.setattr(reporting_upgrade, "_verify_duckdb", boom)
    stdout, stderr = io.StringIO(), io.StringIO()
    code = main(
        ["upgrade-reporting"],
        stdout=stdout,
        stderr=stderr,
        settings=_settings(tmp_path, warehouse),
    )

    receipt = json.loads(stdout.getvalue())
    assert code == EXIT_FAILED
    assert receipt["status"] == "incomplete"
    assert receipt["phase"] == "duckdb_rebuild"
    assert "simulated failure" in receipt["error"]
    assert UPGRADE_COMMAND in receipt["next_step"]
    assert UPGRADE_COMMAND in stderr.getvalue()

    monkeypatch.setattr(reporting_upgrade, "_verify_duckdb", original)
    recovery_code, recovery = run_upgrade(_settings(tmp_path, warehouse), check_only=False)
    assert (recovery_code, recovery["status"]) == (EXIT_COMPLETE, "complete"), recovery
    assert recovery["facts"]["before"] == recovery["facts"]["after"]


def test_upgrade_neither_needs_nor_creates_schema_migrations(tmp_path: Path) -> None:
    warehouse = tmp_path / "warehouse.duckdb"
    _legacy_warehouse(warehouse)  # built by ensure_table, as an installed store is
    store = DuckDBStore.open(str(warehouse), read_only=True)
    assert not _duck_table_exists(store, "schema_migrations")
    store.close()

    code, receipt = run_upgrade(_settings(tmp_path, warehouse), check_only=False)

    assert (code, receipt["status"]) == (EXIT_COMPLETE, "complete"), receipt
    assert "migration_recorded" not in receipt["duckdb"]
    store = DuckDBStore.open(str(warehouse), read_only=True)
    try:
        assert not _duck_table_exists(store, "schema_migrations")
    finally:
        store.close()


def test_upgrade_of_a_chain_built_store_records_the_migration_once(tmp_path: Path) -> None:
    warehouse = tmp_path / "warehouse.duckdb"
    store = DuckDBStore.open(str(warehouse))
    try:
        apply_pending_duckdb_migrations(store.connection, _chain_before_0020(tmp_path / "old"))
        TransformationService(store).load_transactions(
            [
                {"booked_at": "2025-01-05", "account_id": "a", "counterparty_name": "Shop",
                 "amount": "-10", "currency": "EUR", "description": "x"},
                {"booked_at": "2025-01-06", "account_id": "a", "counterparty_name": "Shop",
                 "amount": "-7", "currency": "USD", "description": "y"},
            ],
            run_id="seed",
        )
        store.execute("INSERT INTO mart_monthly_cashflow VALUES ('2025-01', 0, -17, -17, 2)")
    finally:
        store.close()

    code, receipt = run_upgrade(_settings(tmp_path, warehouse), check_only=False)
    assert (code, receipt["status"]) == (EXIT_COMPLETE, "complete"), receipt
    assert receipt["duckdb"]["migration_recorded"] == MIGRATION_VERSION

    again_code, again = run_upgrade(_settings(tmp_path, warehouse), check_only=False)
    assert (again_code, again["status"]) == (EXIT_COMPLETE, "complete")
    store = DuckDBStore.open(str(warehouse))
    try:
        versions = [
            row[0]
            for row in store.fetchall(
                "SELECT version FROM schema_migrations WHERE version = ?", [MIGRATION_VERSION]
            )
        ]
        assert versions == [MIGRATION_VERSION]
        # The migration runner now finds nothing left to apply.
        assert apply_pending_duckdb_migrations(store.connection, MIGRATIONS) == []
        rows = store.fetchall("SELECT currency FROM mart_monthly_cashflow ORDER BY currency")
        assert [row[0] for row in rows] == ["EUR", "USD"]
    finally:
        store.close()


def test_check_reports_without_recording_anything(tmp_path: Path) -> None:
    warehouse = tmp_path / "warehouse.duckdb"
    store = DuckDBStore.open(str(warehouse))
    apply_pending_duckdb_migrations(store.connection, _chain_before_0020(tmp_path / "old"))
    store.close()
    before = warehouse.read_bytes()

    code, receipt = run_upgrade(_settings(tmp_path, warehouse), check_only=True)

    assert (code, receipt["status"]) == (EXIT_COMPLETE, "check_ok")
    assert set(receipt["duckdb"]["states"].values()) == {"legacy", "current"}
    assert receipt["duckdb"]["states"]["mart_monthly_cashflow"] == "legacy"
    assert warehouse.read_bytes() == before


# ---------------------------------------------------------------------------
# Stale legacy relations are refused, never served
# ---------------------------------------------------------------------------


def _legacy_client(tmp_path: Path) -> tuple[TestClient, TransformationService]:
    store = DuckDBStore.memory()
    ts = TransformationService(store)
    for relation in _RELATIONS:
        store.execute(f"DROP TABLE IF EXISTS {relation.name}")
        store.ensure_table(relation.name, relation.columns[:-1])
    service = AccountTransactionService(
        landing_root=tmp_path / "landing",
        metadata_repository=RunMetadataRepository(tmp_path / "runs.db"),
    )
    return TestClient(create_app(service, transformation_service=ts)), ts


def test_legacy_shaped_relation_is_refused_with_503_naming_the_command(tmp_path: Path) -> None:
    client, ts = _legacy_client(tmp_path)
    # An empty legacy relation still lacks the currency column: the schema-level
    # guard refuses it rather than serving it as a valid empty current relation.
    empty = client.get("/reports/monthly-cashflow")
    assert empty.status_code == 503
    assert UPGRADE_COMMAND in empty.json()["error"]

    ts.store.execute("INSERT INTO mart_monthly_cashflow VALUES ('2025-01', 90, -17, 73, 3)")
    response = client.get("/reports/monthly-cashflow")

    assert response.status_code == 503
    body = response.json()
    assert body["relation"] == "mart_monthly_cashflow"
    assert UPGRADE_COMMAND in body["error"]
    assert "rows" not in body


@pytest.mark.parametrize(
    "relation,row",
    [
        ("mart_monthly_cashflow", {"booking_month": "2025-01", "net": "1"}),
        ("mart_usage_vs_price_summary", {"utility_type": "electricity"}),
    ],
)
def test_rows_without_a_currency_column_are_stale(relation: str, row: dict[str, Any]) -> None:
    with pytest.raises(StaleReportingSchemaError) as excinfo:
        assert_currency_current(relation, [row])
    assert UPGRADE_COMMAND in str(excinfo.value)


def test_null_currency_is_stale_only_where_every_row_needs_one() -> None:
    with pytest.raises(StaleReportingSchemaError):
        assert_currency_current("mart_monthly_cashflow", [{"currency": None}])
    # A usage-only row legitimately has no currency.
    assert_currency_current("mart_usage_vs_price_summary", [{"currency": None}])
    assert_currency_current("mart_monthly_cashflow", [])
    assert_currency_current("mart_not_monetary", [{"anything": 1}])


# ---------------------------------------------------------------------------
# Historical snapshots: unavailable, valid-empty, no history
# ---------------------------------------------------------------------------

MONETARY_ROUTES = {
    "/reports/household-overview": "mart_household_overview",
    "/reports/attention-items": "mart_open_attention_items",
    "/reports/recent-changes": "mart_recent_significant_changes",
    "/reports/affordability-ratios": "mart_affordability_ratios",
}
SELF_DESCRIBING_ROUTES = {
    "/reports/recurring-cost-baseline": "mart_recurring_cost_baseline",
    "/reports/subscription-summary": "mart_subscription_summary",
}


def _client(tmp_path: Path) -> tuple[TestClient, TransformationService]:
    service = AccountTransactionService(
        landing_root=tmp_path / "landing",
        metadata_repository=RunMetadataRepository(tmp_path / "runs.db"),
    )
    ts = TransformationService(DuckDBStore.memory())
    return TestClient(create_app(service, transformation_service=ts)), ts


def _put_legacy_snapshot(
    ts: TransformationService, key: str, month: str, rows: list[dict[str, Any]]
) -> str:
    ts.store.ensure_table(SNAPSHOT_TABLE, SNAPSHOT_COLUMNS)
    rows_json = json.dumps(rows, sort_keys=True)
    ts.store.execute(
        f"INSERT INTO {SNAPSHOT_TABLE} (publication_key, reference_month, captured_at, "
        "run_id, row_count, rows_json, contract_version) VALUES (?, ?, ?, ?, ?, ?, NULL)",
        [key, month, "2025-02-01T00:00:00+00:00", "old", len(rows), rows_json],
    )
    return rows_json


@pytest.mark.parametrize("path,relation", sorted(MONETARY_ROUTES.items()))
def test_legacy_monetary_snapshot_is_unavailable_not_empty(
    tmp_path: Path, path: str, relation: str
) -> None:
    client, ts = _client(tmp_path)
    stored = _put_legacy_snapshot(ts, relation, "2025-01", [{"amount": "10.00"}])
    _put_legacy_snapshot(ts, relation, "2025-02", [])

    legacy = client.get(path, params={"as_of": "2025-01"}).json()
    assert legacy["as_of_status"] == "legacy_denomination_unavailable"
    assert legacy["rows"] == []
    assert legacy["snapshot"]["row_count"] == 1
    assert legacy["snapshot"]["run_id"] == "old"
    assert legacy["snapshot"]["projected"] is False

    valid_empty = client.get(path, params={"as_of": "2025-02"}).json()
    assert valid_empty["as_of_status"] == "snapshot"
    assert valid_empty["rows"] == []
    assert valid_empty["snapshot"]["row_count"] == 0

    missing = client.get(path, params={"as_of": "2024-12"}).json()
    assert missing["as_of_status"] == "no_history"
    assert missing["snapshot"] is None

    # Reading never rewrites the stored bytes or fills in a currency.
    (row,) = ts.store.fetchall(
        f"SELECT rows_json, contract_version FROM {SNAPSHOT_TABLE} "
        "WHERE publication_key = ? AND reference_month = ?",
        [relation, "2025-01"],
    )
    assert row == (stored, None)


@pytest.mark.parametrize("path,relation", sorted(SELF_DESCRIBING_ROUTES.items()))
def test_legacy_snapshot_of_rows_that_carry_their_own_currency_stays_readable(
    tmp_path: Path, path: str, relation: str
) -> None:
    client, ts = _client(tmp_path)
    _put_legacy_snapshot(ts, relation, "2025-01", [{"currency": "EUR"}])

    body = client.get(path, params={"as_of": "2025-01"}).json()

    assert body["as_of_status"] == "snapshot"
    assert body["rows"][0]["currency"] == "EUR"


def test_legacy_snapshot_predicate() -> None:
    def snap(version: str | None, rows: list[dict[str, Any]]) -> PublicationSnapshot:
        return PublicationSnapshot("k", "2025-01", "t", None, rows, contract_version=version)

    assert is_legacy_denomination_snapshot("mart_household_overview", snap(None, [{"a": 1}]))
    assert not is_legacy_denomination_snapshot("mart_household_overview", snap(None, []))
    assert not is_legacy_denomination_snapshot("mart_household_overview", snap("2.0.0", [{"a": 1}]))
    assert not is_legacy_denomination_snapshot("mart_subscription_summary", snap(None, [{"a": 1}]))


# ---------------------------------------------------------------------------
# Usage-only rows versus an observed zero bill
# ---------------------------------------------------------------------------


def test_usage_only_is_numeric_zero_without_currency_and_a_zero_bill_keeps_its_currency() -> None:
    service = TransformationService(DuckDBStore.memory())
    service.load_utility_usage(
        [
            {"meter_id": "elec-001", "meter_name": "Main", "utility_type": "electricity",
             "location": "home", "usage_start": "2026-01-01", "usage_end": "2026-01-31",
             "usage_quantity": "320.50", "usage_unit": "kWh", "reading_source": "smart"},
            {"meter_id": "water-001", "meter_name": "Water", "utility_type": "water",
             "location": "home", "usage_start": "2026-01-01", "usage_end": "2026-01-31",
             "usage_quantity": "12700.00", "usage_unit": "liter", "reading_source": "manual"},
        ],
        run_id="usage",
    )
    service.load_bills(
        [
            {"meter_id": "elec-001", "meter_name": "Main", "provider": "Power",
             "utility_type": "electricity", "location": "home",
             "billing_period_start": "2026-01-01", "billing_period_end": "2026-01-31",
             "billed_amount": "0.00", "currency": "USD", "billed_quantity": "320.50",
             "usage_unit": "kWh", "invoice_date": "2026-02-05"},
        ],
        run_id="bills",
    )

    refresh_utility_cost_summary(service.store)
    rows = {row["meter_id"]: row for row in get_utility_cost_summary(service.store)}

    observed = rows["elec-001"]
    assert observed["currency"] == "USD"
    assert Decimal(observed["billed_amount"]) == 0
    assert observed["bill_count"] == 1
    assert observed["coverage_status"] == "matched"

    usage_only = rows["water-001"]
    assert usage_only["currency"] is None
    assert Decimal(usage_only["billed_amount"]) == 0
    assert usage_only["bill_count"] == 0
    assert usage_only["coverage_status"] == "usage_only"


# ---------------------------------------------------------------------------
# Report routes
# ---------------------------------------------------------------------------


def _two_currency_client(tmp_path: Path) -> TestClient:
    client, ts = _client(tmp_path)
    ts.load_transactions(
        [
            {"booked_at": "2025-01-05", "account_id": "a", "counterparty_name": "Shop",
             "amount": "-10", "currency": "EUR", "description": "x"},
            {"booked_at": "2025-01-06", "account_id": "b", "counterparty_name": "Shop",
             "amount": "-7", "currency": "USD", "description": "y"},
            {"booked_at": "2025-01-07", "account_id": "a", "counterparty_name": "Pay",
             "amount": "100", "currency": "EUR", "description": "z"},
        ],
        run_id="seed",
    )
    ts.refresh_publications(
        [
            "mart_monthly_cashflow",
            "mart_monthly_cashflow_by_counterparty",
            "mart_spend_by_category_monthly",
            "mart_spend_by_weekday_hour",
            "mart_account_balance_trend",
            "mart_household_overview",
        ]
    )
    return client


def test_monthly_cashflow_keeps_one_row_per_currency(tmp_path: Path) -> None:
    client = _two_currency_client(tmp_path)

    rows = client.get("/reports/monthly-cashflow").json()["rows"]

    assert sorted((row["currency"], float(row["net"])) for row in rows) == [
        ("EUR", 90.0),
        ("USD", -7.0),
    ]


def test_household_overview_rows_are_per_currency(tmp_path: Path) -> None:
    client = _two_currency_client(tmp_path)

    rows = client.get("/reports/household-overview").json()["rows"]

    assert sorted(row["currency"] for row in rows) == ["EUR", "USD"]


def test_heatmap_requires_a_currency_when_several_and_lists_them(tmp_path: Path) -> None:
    client = _two_currency_client(tmp_path)
    params = {"as_of": "2025-01-31"}

    ambiguous = client.get("/reports/spend-heatmap", params=params).json()
    assert ambiguous["currency"] is None
    assert ambiguous["currencies"] == ["EUR", "USD"]
    assert ambiguous["totals"]["transaction_count"] == 0

    eur = client.get("/reports/spend-heatmap", params={**params, "currency": "EUR"}).json()
    usd = client.get("/reports/spend-heatmap", params={**params, "currency": "USD"}).json()
    assert (eur["currency"], float(eur["totals"]["expense"])) == ("EUR", 10.0)
    assert (usd["currency"], float(usd["totals"]["expense"])) == ("USD", 7.0)
    assert eur["currencies"] == usd["currencies"] == ["EUR", "USD"]


def test_cashflow_map_does_not_blend_currencies(tmp_path: Path) -> None:
    client = _two_currency_client(tmp_path)

    ambiguous = client.get("/reports/cashflow-map").json()
    assert ambiguous["currency"] is None
    assert [item["code"] for item in ambiguous["disclosures"]] == ["multiple_currencies"]
    assert ambiguous["nodes"] == [] and ambiguous["links"] == []

    eur = client.get("/reports/cashflow-map", params={"currency": "EUR"}).json()
    assert eur["currency"] == "EUR"
    assert float(eur["totals"]["income"]) == 100.0
    assert float(eur["totals"]["expense"]) == 10.0


def test_a_single_currency_is_selected_without_a_parameter(tmp_path: Path) -> None:
    client, ts = _client(tmp_path)
    ts.load_transactions(
        [{"booked_at": "2025-01-05", "account_id": "a", "counterparty_name": "Shop",
          "amount": "-10", "currency": "EUR", "description": "x"}],
        run_id="seed",
    )
    ts.refresh_publications(["mart_monthly_cashflow", "mart_spend_by_weekday_hour"])

    heatmap = client.get("/reports/spend-heatmap", params={"as_of": "2025-01-31"}).json()
    cashflow = client.get("/reports/cashflow-map").json()

    assert heatmap["currency"] == "EUR" and heatmap["currencies"] == ["EUR"]
    assert cashflow["currency"] == "EUR"
    # A single currency is selected without a parameter; a freshness disclosure
    # is orthogonal to (and must not be confused with) currency selection.
    assert "multiple_currencies" not in [d["code"] for d in cashflow["disclosures"]]


# ---------------------------------------------------------------------------
# Direct consumers
# ---------------------------------------------------------------------------


def _txn(account: str, amount: str, currency: str, day: str) -> dict[str, Any]:
    return {"booked_at": day, "account_id": account, "counterparty_name": "Shop",
            "amount": amount, "currency": currency, "description": "t"}


def test_scalar_cashflow_is_unavailable_for_several_currencies_and_labelled_for_one() -> None:
    mixed = TransformationService(DuckDBStore.memory())
    mixed.load_transactions(
        [_txn("a", "50", "EUR", "2025-01-05"), _txn("b", "-7", "USD", "2025-01-06")], run_id="m"
    )
    mixed.refresh_publications(["mart_monthly_cashflow"])
    unavailable = ReportingService(mixed).get_current_month_net_cashflow()
    assert unavailable.value is None and unavailable.unit == ""

    single = TransformationService(DuckDBStore.memory())
    single.load_transactions(
        [_txn("a", "50", "EUR", "2025-01-05"), _txn("a", "-10", "EUR", "2025-01-06")], run_id="s"
    )
    single.refresh_publications(["mart_monthly_cashflow"])
    metric = ReportingService(single).get_current_month_net_cashflow()
    assert metric.value == Decimal("40") and metric.unit == "EUR"


def _electricity(service: TransformationService, *, bill: str | None) -> Any:
    service.load_utility_usage(
        [{"meter_id": "elec-001", "meter_name": "Main", "utility_type": "electricity",
          "location": "home", "usage_start": "2026-01-01", "usage_end": "2026-01-31",
          "usage_quantity": "320.50", "usage_unit": "kWh", "reading_source": "smart"}],
        run_id="usage",
    )
    if bill is not None:
        service.load_bills(
            [{"meter_id": "elec-001", "meter_name": "Main", "provider": "Power",
              "utility_type": "electricity", "location": "home",
              "billing_period_start": "2026-01-01", "billing_period_end": "2026-01-31",
              "billed_amount": bill, "currency": "USD", "billed_quantity": "320.50",
              "usage_unit": "kWh", "invoice_date": "2026-02-05"}],
            run_id="bills",
        )
    refresh_utility_cost_summary(service.store)
    return ReportingService(service).get_current_month_electricity_cost()


def test_scalar_electricity_cost_distinguishes_usage_only_from_an_observed_zero() -> None:
    usage_only = _electricity(TransformationService(DuckDBStore.memory()), bill=None)
    assert usage_only.value is None and usage_only.unit == ""

    zero = _electricity(TransformationService(DuckDBStore.memory()), bill="0.00")
    assert zero.value == Decimal("0") and zero.unit == "USD"


class _Reporting(SimpleNamespace):
    def __getattr__(self, name: str) -> Any:  # unconfigured readers return nothing
        if name.startswith("get_"):
            return lambda **_kwargs: []
        raise AttributeError(name)


def _day_row(day: str, amount: str, currency: str | None) -> dict[str, Any]:
    return {"period_day": day, "billed_amount": amount, "currency": currency}


def test_ha_forecast_is_a_number_only_for_one_billed_currency() -> None:
    now = datetime(2026, 1, 15, tzinfo=UTC)

    single = _Reporting(
        get_utility_cost_summary=lambda **_k: [_day_row("2026-01-14", "4.5", "EUR")]
    )
    assert Decimal(_compute_electricity_cost_forecast_today(single, now=now)) == Decimal("4.5")

    mixed = _Reporting(
        get_utility_cost_summary=lambda **_k: [
            _day_row("2026-01-14", "4.5", "EUR"),
            _day_row("2026-01-14", "3", "USD"),
        ]
    )
    assert _compute_electricity_cost_forecast_today(mixed, now=now) == "unavailable"

    usage_only = _Reporting(
        get_utility_cost_summary=lambda **_k: [_day_row("2026-01-14", "0", None)]
    )
    assert _compute_electricity_cost_forecast_today(usage_only, now=now) == "unavailable"

    trend_mixed = _Reporting(
        get_utility_cost_trend_monthly=lambda **_k: [
            {"billing_month": "2025-12", "total_cost": "100", "currency": "EUR"},
            {"billing_month": "2025-12", "total_cost": "90", "currency": "USD"},
        ]
    )
    assert _compute_electricity_cost_forecast_today(trend_mixed, now=now) == "unavailable"


def test_assistant_finance_answer_states_each_currency_separately() -> None:
    reporting = _Reporting(
        get_monthly_cashflow=lambda **_k: [
            {"booking_month": "2025-01", "income": "100", "expense": "10", "net": "90",
             "currency": "EUR"},
            {"booking_month": "2025-01", "income": "0", "expense": "7", "net": "-7",
             "currency": "USD"},
        ],
        get_spend_by_category_monthly=lambda **_k: [
            {"booking_month": "2025-01", "category": "food", "total_expense": "10",
             "currency": "EUR"},
            {"booking_month": "2025-01", "category": "fuel", "total_expense": "7",
             "currency": "USD"},
        ],
    )

    answer = _build_finance_answer(reporting, {}, lambda value: value).answer

    assert "net 90 EUR" in answer and "net -7 USD" in answer
    assert "food in 2025-01 at 10 EUR" in answer and "fuel in 2025-01 at 7 USD" in answer


def test_assistant_utilities_answer_never_calls_usage_only_a_bill() -> None:
    usage_only = _Reporting(
        get_utility_cost_summary=lambda **_k: [
            {"meter_name": "Water", "period": "2026-01", "billed_amount": "0",
             "unit_cost": None, "currency": None, "coverage_status": "usage_only"}
        ]
    )
    answer = _build_utilities_answer(usage_only, {}, lambda value: value).answer
    assert "no bill covers it yet" in answer
    assert "billed at" not in answer

    billed = _Reporting(
        get_utility_cost_summary=lambda **_k: [
            {"meter_name": "Main", "period": "2026-01", "billed_amount": "0",
             "unit_cost": None, "currency": "USD", "coverage_status": "matched"}
        ]
    )
    assert "billed at 0 USD" in _build_utilities_answer(billed, {}, lambda value: value).answer


def test_morning_brief_cashflow_is_stated_per_currency() -> None:
    rows = (
        {"booking_month": "2026-10", "income": "5100", "expense": "3866.5", "net": "1233.5",
         "currency": "EUR"},
        {"booking_month": "2026-10", "income": "0", "expense": "40", "net": "-40",
         "currency": "USD"},
    )
    publications = {
        **_publications(),
        MONTHLY_CASHFLOW_KEY: PublicationInput(
            MONTHLY_CASHFLOW_KEY, rows, _confidence(MONTHLY_CASHFLOW_KEY)
        ),
    }

    section = _section(compose_morning_brief(_inputs(publications=publications)), "money")

    assert [item.item_id for item in section.items] == [
        "money:cashflow:EUR",
        "money:cashflow:USD",
    ]
    eur, usd = section.items
    assert "EUR" in eur.headline and "USD" not in eur.headline
    assert "USD" in usd.headline and "negative" in usd.headline


def test_energy_contract_counts_each_month_once_in_the_contracts_currency() -> None:
    eur = [{**row, "currency": "EUR"} for row in _usage()]
    base = _assess(cost_trend_rows=eur)
    assert base["verdict"] == "alternative_estimated_cheaper"

    foreign = [{**row, "currency": "USD", "usage_amount": "999"} for row in _usage()]
    mixed = _assess(cost_trend_rows=[*eur, *foreign])
    assert mixed["assessment_id"] == base["assessment_id"]
    assert mixed["estimated_annual_cost_current_eur"] == base["estimated_annual_cost_current_eur"]

    only_foreign = _assess(cost_trend_rows=foreign)
    assert only_foreign["verdict"] == "insufficient_evidence"
    assert "usage_history_incomplete" in only_foreign["reason_codes"]


# ---------------------------------------------------------------------------
# PostgreSQL: upgrade and refusal on a disposable server
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def pg_dsn():
    with running_postgres_container() as dsn:
        yield dsn


def _pg_legacy_schema(dsn: str) -> str:
    """A reporting schema holding the legacy shape of every affected relation."""
    schema = f"rep_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(f'CREATE SCHEMA "{schema}"')
        for relation in _RELATIONS:
            columns = ", ".join(
                f'"{name}" {dtype.replace("VARCHAR", "TEXT").replace("DECIMAL", "NUMERIC")}'
                for name, dtype in relation.columns[:-1]
            )
            conn.execute(f'CREATE TABLE "{schema}"."{relation.name}" ({columns})')
        conn.execute(
            f'INSERT INTO "{schema}".mart_monthly_cashflow VALUES (%s, 90, -17, 73, 3)',
            ("2025-01",),
        )
        conn.execute(
            f'INSERT INTO "{schema}"."{SNAPSHOT_TABLE}" VALUES (%s, %s, %s, %s, %s, %s)',
            ("mart_household_overview", "2025-01", "2025-02-01T00:00:00+00:00", "old", 1,
             '[{"cashflow_net":"73"}]'),
        )
        conn.execute(f'GRANT SELECT ON "{schema}".mart_monthly_cashflow TO PUBLIC')
    return schema


def _pg_settings(tmp_path: Path, warehouse: Path, dsn: str, schema: str):
    return replace(
        _settings(tmp_path, warehouse),
        reporting_backend="postgres",
        reporting_postgres_dsn=dsn,
        reporting_schema=schema,
    )


def _pg_one(dsn: str, query: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    with psycopg.connect(dsn, autocommit=True) as conn:
        return [tuple(row) for row in conn.execute(query, params).fetchall()]


def _pg_columns(dsn: str, schema: str, table: str) -> list[str]:
    return [
        row[0]
        for row in _pg_one(
            dsn,
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position",
            (schema, table),
        )
    ]


@pytest.mark.integration
@pytest.mark.slow
def test_postgres_check_is_read_only_and_upgrade_completes_in_one_invocation(
    tmp_path: Path, pg_dsn: str
) -> None:
    warehouse = tmp_path / "warehouse.duckdb"
    _legacy_warehouse(warehouse)
    schema = _pg_legacy_schema(pg_dsn)
    settings = _pg_settings(tmp_path, warehouse, pg_dsn, schema)
    acl = "SELECT relacl::text FROM pg_class WHERE oid = %s::regclass"
    table = f'"{schema}".mart_monthly_cashflow'
    acl_before = _pg_one(pg_dsn, acl, (table,))

    code, check = run_upgrade(settings, check_only=True)
    assert (code, check["status"]) == (EXIT_COMPLETE, "check_ok"), check
    assert "mart_monthly_cashflow" in check["postgres"]["would_alter"]
    assert "currency" not in _pg_columns(pg_dsn, schema, "mart_monthly_cashflow")
    assert "currency" not in _columns(warehouse, "mart_monthly_cashflow")

    code, receipt = run_upgrade(settings, check_only=False)

    assert (code, receipt["status"]) == (EXIT_COMPLETE, "complete"), receipt
    assert receipt["postgres"]["privileges_preserved"] is True
    assert "mart_monthly_cashflow" in receipt["published_relations"]
    rows = _pg_one(
        pg_dsn, f'SELECT currency, net FROM "{schema}".mart_monthly_cashflow ORDER BY currency'
    )
    assert [(currency, float(net)) for currency, net in rows] == [("EUR", 90.0), ("USD", -7.0)]
    assert _pg_one(pg_dsn, acl, (table,)) == acl_before
    # The historical snapshot keeps its bytes and gains no currency or version.
    assert _pg_one(
        pg_dsn,
        f'SELECT rows_json, contract_version FROM "{schema}"."{SNAPSHOT_TABLE}"',
    ) == [('[{"cashflow_net":"73"}]', None)]

    code, again = run_upgrade(settings, check_only=False)
    assert (code, again["status"]) == (EXIT_COMPLETE, "complete")


@pytest.mark.integration
@pytest.mark.slow
def test_postgres_partial_failure_is_incomplete_and_recoverable(
    tmp_path: Path, pg_dsn: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    warehouse = tmp_path / "warehouse.duckdb"
    _legacy_warehouse(warehouse)
    schema = _pg_legacy_schema(pg_dsn)
    settings = _pg_settings(tmp_path, warehouse, pg_dsn, schema)
    original = reporting_upgrade._verify_published

    def boom(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("simulated publish verification failure")

    monkeypatch.setattr(reporting_upgrade, "_verify_published", boom)
    code, receipt = run_upgrade(settings, check_only=False)
    assert code == EXIT_FAILED
    assert receipt["status"] == "incomplete"
    assert receipt["phase"] == "postgres_republish"
    assert UPGRADE_COMMAND in receipt["next_step"]

    monkeypatch.setattr(reporting_upgrade, "_verify_published", original)
    code, recovery = run_upgrade(settings, check_only=False)
    assert (code, recovery["status"]) == (EXIT_COMPLETE, "complete"), recovery


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.parametrize("blocker", ["view", "drift"])
def test_postgres_refusal_changes_neither_store(
    tmp_path: Path, pg_dsn: str, blocker: str
) -> None:
    warehouse = tmp_path / "warehouse.duckdb"
    _legacy_warehouse(warehouse)
    schema = _pg_legacy_schema(pg_dsn)
    if blocker == "view":
        _pg_one_ddl = (
            f'CREATE VIEW "{schema}".dependent AS SELECT * FROM "{schema}".mart_monthly_cashflow'
        )
        expected = "dependent view"
    else:
        _pg_one_ddl = (
            f'ALTER TABLE "{schema}".mart_spend_by_category_monthly ADD COLUMN surprise text'
        )
        expected = "unrecognised column set"
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        conn.execute(_pg_one_ddl)
    pg_before = {
        table: _pg_columns(pg_dsn, schema, table)
        for table in ("mart_monthly_cashflow", "mart_spend_by_category_monthly")
    }

    code, receipt = run_upgrade(_pg_settings(tmp_path, warehouse, pg_dsn, schema), check_only=False)

    assert code == EXIT_REFUSED and receipt["status"] == "refused", receipt
    assert expected in receipt["refusals"][0]
    assert {t: _pg_columns(pg_dsn, schema, t) for t in pg_before} == pg_before
    assert "currency" not in _columns(warehouse, "mart_monthly_cashflow")
    assert "contract_version" not in _columns(warehouse, SNAPSHOT_TABLE)


@pytest.mark.integration
@pytest.mark.slow
def test_postgres_refuses_a_role_that_does_not_own_the_tables(
    tmp_path: Path, pg_dsn: str
) -> None:
    warehouse = tmp_path / "warehouse.duckdb"
    _legacy_warehouse(warehouse)
    schema = _pg_legacy_schema(pg_dsn)
    role = f"reader_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        conn.execute(f"CREATE ROLE {role} LOGIN PASSWORD 'reader'")
        conn.execute(f'GRANT USAGE ON SCHEMA "{schema}" TO {role}')
        conn.execute(f'GRANT SELECT ON ALL TABLES IN SCHEMA "{schema}" TO {role}')
    reader_dsn = pg_dsn.replace("homelab:homelab@", f"{role}:reader@")

    code, receipt = run_upgrade(
        _pg_settings(tmp_path, warehouse, reader_dsn, schema), check_only=False
    )

    assert code == EXIT_REFUSED, receipt
    assert "does not own" in receipt["refusals"][0]
    assert "currency" not in _pg_columns(pg_dsn, schema, "mart_monthly_cashflow")
    assert "currency" not in _columns(warehouse, "mart_monthly_cashflow")


@pytest.mark.integration
@pytest.mark.slow
def test_postgres_republish_refuses_a_trigger_on_a_rebuilt_relation(
    tmp_path: Path, pg_dsn: str
) -> None:
    warehouse = tmp_path / "warehouse.duckdb"
    _legacy_warehouse(warehouse)
    schema = _pg_legacy_schema(pg_dsn)
    # A rebuild-only relation with its exact current shape, plus a trigger that
    # would fire on the TRUNCATE/INSERT republish.
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        conn.execute(
            f'CREATE TABLE "{schema}".mart_household_overview ('
            "current_month TEXT NOT NULL, cashflow_income NUMERIC(18,4) NOT NULL, "
            "cashflow_expense NUMERIC(18,4) NOT NULL, cashflow_net NUMERIC(18,4) NOT NULL, "
            "utility_cost_total NUMERIC(18,4) NOT NULL, "
            "subscription_total_monthly NUMERIC(18,4) NOT NULL, "
            "account_balance_direction TEXT NOT NULL, balance_net_change NUMERIC(18,4) NOT NULL, "
            "currency TEXT NOT NULL)"
        )
        conn.execute(
            f'CREATE FUNCTION "{schema}".noop() RETURNS trigger LANGUAGE plpgsql '
            "AS $$ BEGIN RETURN NEW; END $$"
        )
        conn.execute(
            f'CREATE TRIGGER noop BEFORE INSERT ON "{schema}".mart_household_overview '
            f'FOR EACH ROW EXECUTE FUNCTION "{schema}".noop()'
        )

    code, receipt = run_upgrade(
        _pg_settings(tmp_path, warehouse, pg_dsn, schema), check_only=False
    )

    assert code == EXIT_REFUSED and receipt["status"] == "refused", receipt
    assert "trigger" in receipt["refusals"][0]
    assert "currency" not in _columns(warehouse, "mart_monthly_cashflow")


@pytest.mark.integration
@pytest.mark.slow
def test_postgres_utility_overlap_preserves_selected_periods_without_warehouse(
    pg_dsn: str,
) -> None:
    warehouse = DuckDBStore.memory()
    service = TransformationService(warehouse)
    service.load_bills(
        [
            {**_bill("m1", "200", "EUR"), "billing_period_end": "2026-01-20"},
            {**_bill("m1", "60", "EUR"), "billing_period_start": "2026-01-10"},
        ],
        run_id="bill",
    )
    service.load_utility_usage(
        [
            {**_meter_usage("m1", "50"), "usage_start": day, "usage_end": day}
            for day in ("2026-01-15", "2026-01-17")
        ],
        run_id="usage",
    )
    mart = "mart_utility_cost_summary"
    trend_mart = "mart_utility_cost_trend_monthly"
    service.refresh_publications([mart, trend_mart])
    schema = f"report_overlap_{uuid.uuid4().hex[:8]}"
    published = ReportingService(
        service,
        publication_store=PostgresReportingStore(pg_dsn, schema=schema),
        access_mode=ReportingAccessMode.PUBLISHED,
    )
    published.publish_publications([mart, trend_mart])
    warehouse.execute(f"DELETE FROM {mart}")
    warehouse.execute(f"DELETE FROM {trend_mart}")

    (all_periods,) = published.get_utility_cost_summary()
    assert (all_periods["billed_amount"], all_periods["usage_quantity"]) == (260, 100)
    assert all_periods["usage_record_count"] == 2
    (trend,) = published.get_utility_cost_trend_monthly()
    assert (trend["total_cost"], trend["usage_amount"]) == (260, 100)
    for grain in ("day", "month"):
        (selected,) = published.get_utility_cost_summary(
            granularity=grain, from_period="2026-01-10", to_period="2026-01-31"
        )
        assert (selected["billed_amount"], selected["usage_quantity"]) == (60, 100)
        assert selected["usage_record_count"] == 2
        assert selected["coverage_status"] == "matched"

    for row in published.get_relation_rows(mart):
        assert "usage_observations" not in row

    for invalid in (None, "not json", "[]", "{}", '{"wrong":"quantity"}'):
        with psycopg.connect(pg_dsn) as conn:
            conn.execute(
                f'UPDATE "{schema}".{mart} SET usage_observations = %s '
                "WHERE period_start = DATE '2026-01-01'",
                (invalid,),
            )
        for grain in ("day", "month"):
            with pytest.raises(StaleReportingSchemaError):
                published.get_utility_cost_summary(granularity=grain)
            (selected,) = published.get_utility_cost_summary(
                granularity=grain, from_period="2026-01-10", to_period="2026-01-31"
            )
            assert (selected["billed_amount"], selected["usage_quantity"]) == (60, 100)
