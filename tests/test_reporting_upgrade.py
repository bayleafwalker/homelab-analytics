from __future__ import annotations

import io
import json
from dataclasses import replace
from pathlib import Path

from apps.worker.main import main
from packages.pipelines.reporting_snapshots import SNAPSHOT_TABLE
from packages.pipelines.reporting_upgrade import (
    _REBUILD_ONLY_RELATIONS,
    _RELATIONS,
    EXIT_COMPLETE,
    EXIT_REFUSED,
    _duck_snapshot_evidence,
    _fact_evidence,
    classify_rebuild_only_shape,
    classify_shape,
    run_upgrade,
)
from packages.pipelines.transformation_service import TransformationService
from packages.shared.settings import AppSettings
from packages.storage.duckdb_store import DuckDBStore

LEGACY_SNAPSHOT_ROW = (
    "mart_monthly_cashflow",
    "2025-01",
    "2025-02-01T00:00:00+00:00",
    "old-run",
    1,
    '[{"booking_month":"2025-01","income":"10","net":"10"}]',
)


def _settings(root: Path, warehouse: Path) -> AppSettings:
    return AppSettings(
        data_dir=root,
        landing_root=root / "landing",
        metadata_database_path=root / "metadata" / "runs.db",
        account_transactions_inbox_dir=root / "inbox",
        processed_files_dir=root / "processed",
        failed_files_dir=root / "failed",
        api_host="127.0.0.1",
        api_port=8080,
        web_host="127.0.0.1",
        web_port=8081,
        worker_poll_interval_seconds=1,
        analytics_database_path=warehouse,
    )


def _legacy_warehouse(path: Path) -> None:
    """A populated store whose monetary marts and snapshots have the old shape."""
    store = DuckDBStore.open(str(path))
    try:
        service = TransformationService(store)
        service.load_transactions(
            [
                {"booked_at": "2025-01-05", "account_id": "a", "counterparty_name": "Shop",
                 "amount": "-10", "currency": "EUR", "description": "x"},
                {"booked_at": "2025-01-06", "account_id": "a", "counterparty_name": "Shop",
                 "amount": "-7", "currency": "USD", "description": "y"},
                {"booked_at": "2025-01-07", "account_id": "a", "counterparty_name": "Pay",
                 "amount": "100", "currency": "EUR", "description": "z"},
            ],
            run_id="seed",
        )
        for relation in _RELATIONS:
            store.execute(f"DROP TABLE IF EXISTS {relation.name}")
            store.ensure_table(relation.name, relation.columns[:-1])
        store.execute(
            "INSERT INTO mart_monthly_cashflow VALUES ('2025-01', 90, -17, 73, 3)"
        )
        store.execute(
            f"INSERT INTO {SNAPSHOT_TABLE} VALUES (?, ?, ?, ?, ?, ?)",
            list(LEGACY_SNAPSHOT_ROW),
        )
    finally:
        store.close()


def _columns(path: Path, table: str) -> list[str]:
    store = DuckDBStore.open(str(path), read_only=True)
    try:
        return [row[1] for row in store.fetchall(f"PRAGMA table_info('{table}')")]
    finally:
        store.close()


def test_classify_shape_recognises_only_known_states() -> None:
    columns = _RELATIONS[0].columns
    observed = [(name, dtype.replace(" NOT NULL", "")) for name, dtype in columns]
    assert classify_shape([], columns, postgres=False) == "absent"
    assert classify_shape(observed[:-1], columns, postgres=False) == "legacy"
    assert classify_shape(observed, columns, postgres=False) == "current"
    assert classify_shape([*observed, ("extra", "VARCHAR")], columns, postgres=False) == "unknown"
    assert classify_shape(list(reversed(observed)), columns, postgres=False) == "unknown"


def test_classify_shape_maps_postgres_date_columns() -> None:
    """The PostgreSQL preflight maps DATE columns, not just text/numeric/int."""
    relation = next(r for r in _RELATIONS if r.name == "mart_spend_by_weekday_hour")
    observed = [
        ("booked_at", "date"),
        ("day_of_week", "integer"),
        ("hour_of_day", "integer"),
        ("total_expense", "numeric"),
        ("transaction_count", "integer"),
        ("currency", "text"),
    ]
    assert classify_shape(observed, relation.columns, postgres=True) == "current"
    assert classify_shape(observed[:-1], relation.columns, postgres=True) == "legacy"


def test_classify_rebuild_only_shape_accepts_only_absent_or_current() -> None:
    relation = next(r for r in _REBUILD_ONLY_RELATIONS if r.name == "mart_household_overview")
    observed = [(name, dtype.replace(" NOT NULL", "")) for name, dtype in relation.columns]
    assert classify_rebuild_only_shape([], relation.columns, postgres=False) == "absent"
    assert classify_rebuild_only_shape(observed, relation.columns, postgres=False) == "current"
    # An extra column, a missing column, or type drift is unknown (never legacy).
    assert (
        classify_rebuild_only_shape([*observed, ("operator_note", "VARCHAR")],
                                    relation.columns, postgres=False)
        == "unknown"
    )
    assert classify_rebuild_only_shape(observed[:-1], relation.columns, postgres=False) == "unknown"


def test_classify_rebuild_only_shape_ignores_runtime_optional_columns() -> None:
    relation = next(r for r in _REBUILD_ONLY_RELATIONS if r.name == "mart_affordability_ratios")
    observed = [(name, dtype.replace(" NOT NULL", "")) for name, dtype in relation.columns]
    # The self-healed `state` column may be absent (pre-heal) or present with
    # its documented VARCHAR type (post-heal).
    assert (
        classify_rebuild_only_shape(
            observed, relation.columns, postgres=False, optional=relation.optional
        )
        == "current"
    )
    assert (
        classify_rebuild_only_shape(
            [*observed, ("state", "VARCHAR")], relation.columns, postgres=False,
            optional=relation.optional,
        )
        == "current"
    )
    # A known optional name with a foreign type is still refused.
    assert (
        classify_rebuild_only_shape(
            [*observed, ("state", "INTEGER")], relation.columns, postgres=False,
            optional=relation.optional,
        )
        == "unknown"
    )
    # An unrelated extra column is still refused.
    assert (
        classify_rebuild_only_shape(
            [*observed, ("operator_note", "VARCHAR")], relation.columns, postgres=False,
            optional=relation.optional,
        )
        == "unknown"
    )


def test_check_is_read_only_and_reports_legacy(tmp_path: Path) -> None:
    warehouse = tmp_path / "warehouse.duckdb"
    _legacy_warehouse(warehouse)
    before = warehouse.read_bytes()

    code, receipt = run_upgrade(_settings(tmp_path, warehouse), check_only=True)

    assert code == EXIT_COMPLETE
    assert receipt["status"] == "check_ok"
    assert receipt["duckdb"]["states"]["mart_monthly_cashflow"] == "legacy"
    assert "currency" not in _columns(warehouse, "mart_monthly_cashflow")
    assert warehouse.read_bytes() == before


def test_upgrade_separates_currencies_and_preserves_evidence(tmp_path: Path) -> None:
    warehouse = tmp_path / "warehouse.duckdb"
    _legacy_warehouse(warehouse)
    store = DuckDBStore.open(str(warehouse), read_only=True)
    facts_before = _fact_evidence(store)
    snapshots_before = _duck_snapshot_evidence(store)
    store.close()
    assert facts_before["fact_transaction"]["rows"] == 3

    code, receipt = run_upgrade(_settings(tmp_path, warehouse), check_only=False)

    assert (code, receipt["status"]) == (EXIT_COMPLETE, "complete"), receipt
    store = DuckDBStore.open(str(warehouse), read_only=True)
    try:
        assert _fact_evidence(store) == facts_before
        assert _duck_snapshot_evidence(store) == snapshots_before
        rows = store.fetchall(
            "SELECT currency, income, expense, net FROM mart_monthly_cashflow "
            "ORDER BY currency"
        )
        assert [row[0] for row in rows] == ["EUR", "USD"]
        assert float(rows[0][3]) == 90.0 and float(rows[1][3]) == -7.0
        legacy = store.fetchall(
            f"SELECT contract_version, rows_json FROM {SNAPSHOT_TABLE}"
        )
        assert legacy == [(None, LEGACY_SNAPSHOT_ROW[5])]
    finally:
        store.close()

    again_code, again = run_upgrade(_settings(tmp_path, warehouse), check_only=False)
    assert (again_code, again["status"]) == (EXIT_COMPLETE, "complete")


def test_unknown_drift_is_refused_before_any_change(tmp_path: Path) -> None:
    warehouse = tmp_path / "warehouse.duckdb"
    _legacy_warehouse(warehouse)
    store = DuckDBStore.open(str(warehouse))
    store.execute("ALTER TABLE mart_spend_by_category_monthly ADD COLUMN surprise VARCHAR")
    store.close()
    before = {t: _columns(warehouse, t) for t in ("mart_monthly_cashflow", SNAPSHOT_TABLE)}

    code, receipt = run_upgrade(_settings(tmp_path, warehouse), check_only=False)

    assert code == EXIT_REFUSED and receipt["status"] == "refused"
    assert "mart_spend_by_category_monthly" in receipt["refusals"][0]
    assert {t: _columns(warehouse, t) for t in before} == before


def test_unknown_column_on_rebuilt_relation_is_refused_and_preserved(tmp_path: Path) -> None:
    warehouse = tmp_path / "warehouse.duckdb"
    _legacy_warehouse(warehouse)
    store = DuckDBStore.open(str(warehouse))
    try:
        for relation in _REBUILD_ONLY_RELATIONS:
            store.ensure_table(relation.name, relation.columns)
        store.execute("ALTER TABLE mart_household_overview ADD COLUMN operator_note VARCHAR")
        store.execute(
            "INSERT INTO mart_household_overview "
            "(current_month, cashflow_income, cashflow_expense, cashflow_net, "
            "utility_cost_total, subscription_total_monthly, account_balance_direction, "
            "balance_net_change, currency, operator_note) "
            "VALUES ('2025-01', 0, 0, 0, 0, 0, 'flat', 0, 'EUR', 'foreign sentinel')"
        )
    finally:
        store.close()

    # --check must refuse the unknown column, not report check_ok.
    code, check = run_upgrade(_settings(tmp_path, warehouse), check_only=True)
    assert code == EXIT_REFUSED
    assert "mart_household_overview" in check["refusals"][0]

    # The real upgrade must refuse before mutation and preserve the sentinel.
    code, receipt = run_upgrade(_settings(tmp_path, warehouse), check_only=False)
    assert code == EXIT_REFUSED
    assert "mart_household_overview" in receipt["refusals"][0]
    assert "operator_note" in _columns(warehouse, "mart_household_overview")
    store = DuckDBStore.open(str(warehouse), read_only=True)
    try:
        rows = store.fetchall(
            "SELECT operator_note FROM mart_household_overview WHERE operator_note IS NOT NULL"
        )
        assert [row[0] for row in rows] == ["foreign sentinel"]
    finally:
        store.close()


def test_missing_warehouse_is_refused_and_not_created(tmp_path: Path) -> None:
    warehouse = tmp_path / "absent.duckdb"
    code, receipt = run_upgrade(_settings(tmp_path, warehouse), check_only=False)
    assert code == EXIT_REFUSED
    assert not warehouse.exists()


def test_postgres_backend_without_dsn_is_refused(tmp_path: Path) -> None:
    warehouse = tmp_path / "warehouse.duckdb"
    _legacy_warehouse(warehouse)
    settings = _settings(tmp_path, warehouse)
    settings = replace(settings, reporting_backend="postgres")
    code, receipt = run_upgrade(settings, check_only=True)
    assert code == EXIT_REFUSED
    assert "POSTGRES_DSN" in receipt["refusals"][0]
    assert "currency" not in _columns(warehouse, "mart_monthly_cashflow")


def test_cli_entrypoint_dispatches_without_control_plane(tmp_path: Path) -> None:
    warehouse = tmp_path / "warehouse.duckdb"
    _legacy_warehouse(warehouse)
    stdout, stderr = io.StringIO(), io.StringIO()

    code = main(
        ["upgrade-reporting", "--check"],
        stdout=stdout,
        stderr=stderr,
        settings=_settings(tmp_path, warehouse),
    )

    assert code == 0, stderr.getvalue()
    assert json.loads(stdout.getvalue())["status"] == "check_ok"
    assert not (tmp_path / "metadata" / "runs.db").exists()
