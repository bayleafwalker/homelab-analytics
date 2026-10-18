"""As-of history: dated snapshots of current-only reporting publications."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.domains.finance.pipelines.account_transaction_service import (
    AccountTransactionService,
)
from packages.pipelines.promotion_types import PromotionResult
from packages.pipelines.reporting_service import (
    ReportingAccessMode,
    ReportingService,
    publish_promotion_reporting,
)
from packages.pipelines.reporting_snapshots import (
    SNAPSHOT_COLUMNS,
    SNAPSHOT_PUBLICATIONS,
    SNAPSHOT_TABLE,
    is_reference_month,
    project_snapshot_rows,
)
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.run_metadata import RunMetadataRepository

MIGRATION = (
    Path(__file__).resolve().parent.parent
    / "migrations"
    / "duckdb"
    / "0016_reporting_publication_snapshot.sql"
)


def _load_month(ts: TransformationService, month: str, *, run_id: str, rent: str = "-900.00") -> None:
    ts.load_transactions(
        [
            {
                "booked_at": f"{month}-03T08:00:00+00:00",
                "account_id": "checking",
                "counterparty_name": "Employer",
                "amount": "2500.00",
                "currency": "EUR",
                "description": "salary",
            },
            {
                "booked_at": f"{month}-05T08:00:00+00:00",
                "account_id": "checking",
                "counterparty_name": "Landlord",
                "amount": rent,
                "currency": "EUR",
                "description": "rent",
            },
        ],
        run_id=run_id,
    )
    ts.refresh_publications(
        [
            "mart_monthly_cashflow",
            "mart_household_overview",
            "mart_open_attention_items",
            "mart_recent_significant_changes",
            "mart_affordability_ratios",
            "mart_recurring_cost_baseline",
        ]
    )


def _capture(rs: ReportingService, *, run_id: str, at: datetime) -> list[str]:
    return rs.capture_publication_snapshots(
        sorted(SNAPSHOT_PUBLICATIONS | {"mart_monthly_cashflow"}),
        run_id=run_id,
        captured_at=at,
    )


def test_reference_month_validation() -> None:
    assert is_reference_month("2026-01")
    assert not is_reference_month("2026-13")
    assert not is_reference_month("2026-1")
    assert not is_reference_month(None)


def test_snapshot_is_keyed_by_newest_published_month() -> None:
    ts = TransformationService(DuckDBStore.memory())
    rs = ReportingService(ts)
    _load_month(ts, "2026-01", run_id="run-jan")

    captured = _capture(rs, run_id="run-jan", at=datetime(2026, 2, 2, tzinfo=UTC))

    # Month-keyed marts are never snapshotted.
    assert "mart_monthly_cashflow" not in captured
    assert "mart_household_overview" in captured
    snapshot = rs.get_publication_snapshot("mart_household_overview", "2026-01")
    assert snapshot is not None
    assert snapshot.reference_month == "2026-01"
    assert snapshot.run_id == "run-jan"
    assert snapshot.captured_at == "2026-02-02T00:00:00+00:00"
    assert snapshot.rows[0]["current_month"] == "2026-01"
    # Values are serialised the way the API serialises them.
    assert snapshot.rows[0]["cashflow_net"] == "1600.0000"
    # Before the first snapshot there is no history, not current data.
    assert rs.get_publication_snapshot("mart_household_overview", "2025-12") is None


def test_later_month_keeps_earlier_snapshot_and_same_month_replaces() -> None:
    ts = TransformationService(DuckDBStore.memory())
    rs = ReportingService(ts)
    _load_month(ts, "2026-01", run_id="run-jan")
    _capture(rs, run_id="run-jan", at=datetime(2026, 2, 2, tzinfo=UTC))
    _load_month(ts, "2026-02", run_id="run-feb", rent="-1200.00")
    _capture(rs, run_id="run-feb", at=datetime(2026, 3, 2, tzinfo=UTC))

    january = rs.get_publication_snapshot("mart_household_overview", "2026-01")
    february = rs.get_publication_snapshot("mart_household_overview", "2026-02")
    assert january is not None and february is not None
    assert january.rows[0]["cashflow_net"] == "1600.0000"
    assert february.rows[0]["cashflow_net"] == "1300.0000"
    assert rs.list_publication_snapshot_months("mart_household_overview") == [
        "2026-01",
        "2026-02",
    ]

    # A second refresh in February supersedes the first February snapshot.
    _capture(rs, run_id="run-feb-2", at=datetime(2026, 3, 9, tzinfo=UTC))
    rows = ts.store.fetchall(
        f"SELECT run_id FROM {SNAPSHOT_TABLE} "
        "WHERE publication_key = 'mart_household_overview' AND reference_month = '2026-02'"
    )
    assert rows == [("run-feb-2",)]


def test_retention_keeps_newest_reference_months() -> None:
    ts = TransformationService(DuckDBStore.memory())
    rs = ReportingService(ts, snapshot_retention_months=2)
    for index, month in enumerate(("2026-01", "2026-02", "2026-03"), start=1):
        _load_month(ts, month, run_id=f"run-{month}")
        _capture(rs, run_id=f"run-{month}", at=datetime(2026, index + 1, 1, tzinfo=UTC))

    assert rs.list_publication_snapshot_months("mart_open_attention_items") == [
        "2026-02",
        "2026-03",
    ]
    assert rs.get_publication_snapshot("mart_open_attention_items", "2026-01") is None


def test_nothing_is_captured_before_any_month_is_published() -> None:
    ts = TransformationService(DuckDBStore.memory())
    rs = ReportingService(ts)
    ts.refresh_publications(["mart_household_overview"])
    assert _capture(rs, run_id="run-empty", at=datetime(2026, 1, 1, tzinfo=UTC)) == []


def test_invalid_month_is_rejected() -> None:
    rs = ReportingService(TransformationService(DuckDBStore.memory()))
    with pytest.raises(ValueError):
        rs.get_publication_snapshot("mart_household_overview", "2026-1")


class _RecordingSessions:
    """Stands in for WarehouseSessionManager: one lease per call, mode recorded."""

    def __init__(self, service: TransformationService) -> None:
        self._service = service
        self.calls: list[tuple[str, bool]] = []

    def call(self, label, fn, *, write):
        self.calls.append((label, write))
        return fn(self._service)


class _SessionFacade:
    """Like WarehouseSessionTransformationService: only ``store`` and sessions."""

    def __init__(self, service: TransformationService) -> None:
        self.warehouse_sessions = _RecordingSessions(service)
        self._service = service

    @property
    def store(self):
        return self._service.store


def test_warehouse_snapshots_use_one_lease_per_operation_and_no_facade_methods() -> None:
    ts = TransformationService(DuckDBStore.memory())
    _load_month(ts, "2026-01", run_id="run-jan")
    facade = _SessionFacade(ts)
    rs = ReportingService(facade)  # type: ignore[arg-type]

    captured = rs.capture_publication_snapshots(["mart_household_overview"], run_id="run-jan")
    assert captured == ["mart_household_overview"]
    assert rs.get_publication_snapshot("mart_household_overview", "2026-01") is not None
    assert rs.list_publication_snapshot_months("mart_household_overview") == ["2026-01"]

    # Reads lease read-only handles; the delete + insert + prune is one write lease.
    assert facade.warehouse_sessions.calls == [
        ("reporting_snapshots.reference_month", False),
        ("reporting_snapshots.record", True),
        ("reporting_snapshots.read", False),
        ("reporting_snapshots.months", False),
    ]
    # The snapshot store adds nothing to the TransformationService surface.
    for name in (
        "record_publication_snapshot",
        "get_publication_snapshot",
        "list_publication_snapshot_months",
        "get_snapshot_reference_month",
    ):
        assert not hasattr(TransformationService, name)


class _PublishedStoreWithoutSnapshots:
    def table_exists(self, table_name: str) -> bool:
        return False


def test_published_mode_never_reads_the_warehouse_copy() -> None:
    ts = TransformationService(DuckDBStore.memory())
    _load_month(ts, "2026-01", run_id="run-jan")
    _capture(ReportingService(ts), run_id="run-jan", at=datetime(2026, 2, 2, tzinfo=UTC))

    published = ReportingService(
        ts,
        publication_store=_PublishedStoreWithoutSnapshots(),  # type: ignore[arg-type]
        access_mode=ReportingAccessMode.PUBLISHED,
    )
    assert published.get_publication_snapshot("mart_household_overview", "2026-01") is None

    preferred = ReportingService(
        ts,
        publication_store=_PublishedStoreWithoutSnapshots(),  # type: ignore[arg-type]
        access_mode=ReportingAccessMode.PREFER_PUBLISHED,
    )
    assert preferred.get_publication_snapshot("mart_household_overview", "2026-01") is not None


def test_publish_promotion_reporting_captures_snapshots_on_the_duckdb_path() -> None:
    ts = TransformationService(DuckDBStore.memory())
    rs = ReportingService(ts, access_mode=ReportingAccessMode.WAREHOUSE)
    _load_month(ts, "2026-04", run_id="run-apr")

    published = publish_promotion_reporting(
        rs,
        PromotionResult(
            run_id="run-apr",
            facts_loaded=2,
            marts_refreshed=["mart_monthly_cashflow", "mart_household_overview"],
            publication_keys=["mart_monthly_cashflow"],
        ),
    )

    # Nothing is pushed on the DuckDB path; the snapshot is still taken.
    assert published == []
    assert rs.list_publication_snapshot_months("mart_household_overview") == ["2026-04"]
    assert rs.list_publication_snapshot_months("mart_open_attention_items") == []


def test_migration_matches_runtime_columns() -> None:
    store = DuckDBStore.memory()
    store.execute(MIGRATION.read_text())
    described = store.fetchall(f"DESCRIBE {SNAPSHOT_TABLE}")
    assert [row[0] for row in described] == [name for name, _ in SNAPSHOT_COLUMNS]


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def _client(tmp_path: Path) -> tuple[TestClient, TransformationService]:
    service = AccountTransactionService(
        landing_root=tmp_path / "landing",
        metadata_repository=RunMetadataRepository(tmp_path / "runs.db"),
    )
    ts = TransformationService(DuckDBStore.memory())
    return TestClient(create_app(service, transformation_service=ts)), ts


def _seed_snapshot(ts: TransformationService, month: str) -> None:
    _load_month(ts, month, run_id=f"run-{month}")
    rs = ReportingService(ts)
    _capture(rs, run_id=f"run-{month}", at=datetime(2026, 5, 1, tzinfo=UTC))


@pytest.mark.parametrize(
    "path",
    [
        "/reports/household-overview",
        "/reports/attention-items",
        "/reports/recent-changes",
        "/reports/affordability-ratios",
        "/reports/recurring-cost-baseline",
        "/reports/subscription-summary",
    ],
)
def test_as_of_endpoints_report_current_snapshot_or_no_history(tmp_path: Path, path: str) -> None:
    client, ts = _client(tmp_path)
    _seed_snapshot(ts, "2026-04")

    current = client.get(path)
    assert current.status_code == 200
    assert current.json()["as_of_status"] == "current"
    assert current.json()["snapshot"] is None

    snapshot = client.get(path, params={"as_of": "2026-04"})
    assert snapshot.status_code == 200
    body = snapshot.json()
    assert body["as_of"] == "2026-04"
    assert body["as_of_status"] == "snapshot"
    assert body["snapshot"]["reference_month"] == "2026-04"
    assert body["snapshot"]["run_id"] == "run-2026-04"

    missing = client.get(path, params={"as_of": "2026-01"})
    assert missing.status_code == 200
    assert missing.json()["as_of_status"] == "no_history"
    assert missing.json()["rows"] == []

    assert client.get(path, params={"as_of": "April"}).status_code == 400


def test_household_overview_as_of_returns_the_snapshot_rows(tmp_path: Path) -> None:
    client, ts = _client(tmp_path)
    _seed_snapshot(ts, "2026-04")
    _load_month(ts, "2026-05", run_id="run-may", rent="-2000.00")

    current = client.get("/reports/household-overview").json()["rows"][0]
    past = client.get("/reports/household-overview", params={"as_of": "2026-04"}).json()
    assert current["current_month"] == "2026-05"
    assert past["rows"][0]["current_month"] == "2026-04"
    assert float(past["rows"][0]["cashflow_net"]) == 1600.0


def test_subscription_summary_as_of_applies_filters(tmp_path: Path) -> None:
    client, ts = _client(tmp_path)
    _load_month(ts, "2026-04", run_id="run-apr")
    ts.load_subscriptions(
        [
            {
                "contract_id": "sub-stream",
                "service_name": "Stream",
                "provider": "Stream Oy",
                "contract_type": "subscription",
                "billing_cycle": "monthly",
                "amount": "15.99",
                "currency": "EUR",
                "start_date": "2025-01-15",
                "end_date": None,
            }
        ],
        run_id="run-sub",
    )
    ts.refresh_publications(["mart_subscription_summary"])
    _capture(ReportingService(ts), run_id="run-sub", at=datetime(2026, 5, 1, tzinfo=UTC))

    matched = client.get(
        "/reports/subscription-summary", params={"as_of": "2026-04", "currency": "EUR"}
    ).json()
    assert matched["as_of_status"] == "snapshot"
    assert [row["contract_name"] for row in matched["rows"]] == ["Stream"]
    assert matched["currency"] == "EUR"
    filtered = client.get(
        "/reports/subscription-summary", params={"as_of": "2026-04", "currency": "USD"}
    ).json()
    assert filtered["as_of_status"] == "snapshot"
    assert filtered["rows"] == []


# Snapshots captured before a mart column change
# ---------------------------------------------------------------------------


def _rewrite_snapshot_rows(ts: TransformationService, publication_key: str, edit) -> None:
    """Stand in for a snapshot captured under an older mart schema."""
    (row,) = ts.store.fetchall(
        f"SELECT rows_json FROM {SNAPSHOT_TABLE} WHERE publication_key = ?",
        [publication_key],
    )
    rows = [edit(dict(item)) for item in json.loads(row[0])]
    ts.store.execute(
        f"UPDATE {SNAPSHOT_TABLE} SET rows_json = ? WHERE publication_key = ?",
        [json.dumps(rows), publication_key],
    )


def test_project_snapshot_rows_fits_rows_to_current_columns() -> None:
    projection = project_snapshot_rows(
        [{"a": 1, "old": "x"}, {"a": 2, "b": 3, "old": "y"}], ["a", "b"]
    )
    assert projection.rows == [{"a": 1, "b": None}, {"a": 2, "b": 3}]
    assert projection.missing_columns == ("b",)
    assert projection.dropped_columns == ("old",)
    assert projection.projected is True

    exact = project_snapshot_rows([{"a": 1, "b": 2}], ["a", "b"])
    assert exact.projected is False
    assert exact.rows == [{"a": 1, "b": 2}]


def test_as_of_read_of_a_pre_change_snapshot_is_projected(tmp_path: Path) -> None:
    client, ts = _client(tmp_path)
    _seed_snapshot(ts, "2026-04")

    def older_schema(row: dict) -> dict:
        # A NOT NULL column the mart gained later, a column it has since
        # dropped, and a value whose column type changed.
        row.pop("currency")
        row["legacy_score"] = 7
        row["account_balance_direction"] = {"was": "an object"}
        return row

    _rewrite_snapshot_rows(ts, "mart_household_overview", older_schema)

    response = client.get("/reports/household-overview", params={"as_of": "2026-04"})

    assert response.status_code == 200
    body = response.json()
    row = body["rows"][0]
    assert row["currency"] is None
    assert row["account_balance_direction"] is None
    assert "legacy_score" not in row
    assert row["current_month"] == "2026-04"
    snapshot = body["snapshot"]
    assert snapshot["projected"] is True
    assert snapshot["missing_columns"] == ["currency"]
    assert snapshot["dropped_columns"] == ["legacy_score"]
    assert snapshot["incompatible_columns"] == ["account_balance_direction"]


def test_as_of_read_of_a_current_shape_snapshot_is_not_flagged(tmp_path: Path) -> None:
    client, ts = _client(tmp_path)
    _seed_snapshot(ts, "2026-04")

    snapshot = client.get(
        "/reports/attention-items", params={"as_of": "2026-04"}
    ).json()["snapshot"]

    assert snapshot["projected"] is False
    assert snapshot["missing_columns"] == []
    assert snapshot["dropped_columns"] == []
    assert snapshot["incompatible_columns"] == []
