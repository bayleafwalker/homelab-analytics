from __future__ import annotations

from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.domains.finance.pipelines.account_transaction_service import AccountTransactionService
from packages.domains.finance.pipelines.spend_heatmap import (
    build_spend_heatmap,
    spend_heatmap_window,
)
from packages.pipelines.household_packages import BUILTIN_TRANSFORMATION_PACKAGE_SPECS
from packages.pipelines.household_reporting import PUBLICATION_RELATIONS
from packages.pipelines.household_transformation_refresh import (
    BUILTIN_PUBLICATION_REFRESH_HANDLERS,
)
from packages.pipelines.reporting_service import ReportingService
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.run_metadata import RunMetadataRepository

MIGRATION = Path(__file__).resolve().parents[1] / "migrations" / "duckdb" / (
    "0018_spend_by_weekday_hour_mart.sql"
)


def _row(booked_at: str, hour: int | None, amount: str, count: int = 1) -> dict[str, object]:
    day = date.fromisoformat(booked_at)
    return {
        "booked_at": day,
        "day_of_week": day.isoweekday(),
        "hour_of_day": hour,
        "total_expense": amount,
        "transaction_count": count,
    }


def _tx(booked_at: str, counterparty: str, amount: str) -> dict[str, object]:
    return {
        "booked_at": booked_at,
        "account_id": "CHK-001",
        "counterparty_name": counterparty,
        "amount": amount,
        "currency": "EUR",
        "description": "",
    }


def test_window_is_inclusive_of_both_ends() -> None:
    assert spend_heatmap_window(date(2026, 3, 28), 28) == (date(2026, 3, 1), date(2026, 3, 28))
    assert spend_heatmap_window(date(2026, 3, 28), 1) == (date(2026, 3, 28), date(2026, 3, 28))


def test_matrix_is_seven_by_twenty_four_and_sums_buckets() -> None:
    # 2026-03-02 is a Monday, 2026-03-08 a Sunday.
    payload = build_spend_heatmap(
        [
            _row("2026-03-02", 9, "12.50"),
            _row("2026-03-02", 9, "7.50", count=2),
            _row("2026-03-08", 23, "40.00"),
        ],
        window_days=28,
    )
    assert len(payload["cells"]) == 7
    assert all(len(row) == 24 for row in payload["cells"])
    assert len(payload["counts"]) == 7 and all(len(row) == 24 for row in payload["counts"])
    assert payload["cells"][0][9] == "20.00"
    assert payload["counts"][0][9] == 3
    assert payload["cells"][6][23] == "40.00"
    assert payload["max_cell"] == "40.00"
    assert payload["coverage"] == "timed"
    assert payload["window_end"] == "2026-03-08"
    assert payload["window_start"] == "2026-02-09"
    assert payload["hour_basis"] == "utc"
    assert payload["day_labels"][0] == "Mon"
    assert payload["totals"] == {
        "expense": "60.00",
        "timed_expense": "60.00",
        "untimed_expense": "0.00",
        "transaction_count": 4,
        "timed_count": 4,
        "untimed_count": 0,
        "active_days": 2,
    }


def test_date_only_spend_is_kept_out_of_the_hour_grid() -> None:
    payload = build_spend_heatmap(
        [_row("2026-03-03", None, "84.15"), _row("2026-03-03", 14, "5.00")],
    )
    # Tuesday row: hour 0 must stay empty, the date-only amount goes to untimed.
    assert payload["cells"][1][0] == "0.00"
    assert payload["cells"][1][14] == "5.00"
    assert payload["untimed"][1] == "84.15"
    assert payload["untimed_counts"][1] == 1
    assert payload["max_untimed"] == "84.15"
    assert payload["coverage"] == "mixed"
    only_dates = build_spend_heatmap([_row("2026-03-03", None, "84.15")])
    assert only_dates["coverage"] == "date_only"
    assert only_dates["max_cell"] == "0.00"


def test_rows_outside_the_window_are_ignored_and_explicit_end_wins() -> None:
    rows = [_row("2026-01-05", 10, "99.00"), _row("2026-03-02", 10, "1.00")]
    payload = build_spend_heatmap(rows, window_days=28)
    assert payload["cells"][0][10] == "1.00"
    assert payload["data_through"] == "2026-03-02"
    rewound = build_spend_heatmap(rows, window_days=7, end=date(2026, 1, 7))
    assert rewound["cells"][0][10] == "99.00"
    assert rewound["window_end"] == "2026-01-07"
    assert rewound["data_through"] == "2026-03-02"


def test_empty_input_is_sparse_safe() -> None:
    payload = build_spend_heatmap([])
    assert payload["coverage"] == "empty"
    assert payload["window_start"] is None and payload["window_end"] is None
    assert payload["cells"] == [["0.00"] * 24 for _ in range(7)]
    assert payload["untimed"] == ["0.00"] * 7
    assert payload["totals"]["transaction_count"] == 0


def test_window_bounds_are_validated() -> None:
    with pytest.raises(ValueError):
        build_spend_heatmap([], window_days=0)
    with pytest.raises(ValueError):
        build_spend_heatmap([], window_days=367)


def test_publication_is_registered_on_the_reporting_layer() -> None:
    assert "mart_spend_by_weekday_hour" in PUBLICATION_RELATIONS
    assert "mart_spend_by_weekday_hour" in BUILTIN_PUBLICATION_REFRESH_HANDLERS
    spec = next(
        spec
        for spec in BUILTIN_TRANSFORMATION_PACKAGE_SPECS
        if spec.transformation_package_id == "builtin_account_transactions"
    )
    assert "mart_spend_by_weekday_hour" in spec.publication_keys
    assert "mart_spend_by_weekday_hour" in spec.refresh_publication_keys
    migration = MIGRATION.read_text()
    assert migration.count("CREATE TABLE IF NOT EXISTS mart_spend_by_weekday_hour") == 1
    for column, _ in PUBLICATION_RELATIONS["mart_spend_by_weekday_hour"].columns:
        assert column in migration


def test_mart_refresh_keeps_time_of_day_and_flags_date_only_rows() -> None:
    service = TransformationService(DuckDBStore.memory())
    service.load_transactions(
        [
            _tx("2026-03-02T09:15:00+00:00", "Bakery", "-4.50"),
            _tx("2026-03-02T09:45:00Z", "Cafe", "-3.20"),
            _tx("2026-03-03", "Electric Utility", "-84.15"),
            _tx("2026-03-03", "Employer", "2450.00"),
        ],
        run_id="run-001",
    )
    assert service.refresh_publications(["mart_spend_by_weekday_hour"]) == [
        "mart_spend_by_weekday_hour"
    ]
    reporting = ReportingService(service)
    rows = reporting.get_spend_by_weekday_hour()
    assert len(rows) == 2
    by_key = {(row["booked_at"], row["hour_of_day"]): row for row in rows}
    monday = by_key[(date(2026, 3, 2), 9)]
    assert monday["day_of_week"] == 1
    assert str(monday["total_expense"]) == "7.7000"
    assert monday["transaction_count"] == 2
    tuesday = by_key[(date(2026, 3, 3), None)]
    assert tuesday["day_of_week"] == 2
    assert str(tuesday["total_expense"]) == "84.1500"
    windowed = reporting.get_spend_by_weekday_hour(from_date=date(2026, 3, 3))
    assert [row["booked_at"] for row in windowed] == [date(2026, 3, 3)]


def test_spend_heatmap_endpoint_reads_the_reporting_mart() -> None:
    with TemporaryDirectory() as temp_dir:
        service = TransformationService(DuckDBStore.memory())
        service.load_transactions(
            [
                _tx("2026-03-02T18:05:00Z", "Grocer", "-42.00"),
                _tx("2026-03-04", "Power Co", "-60.00"),
            ],
            run_id="run-001",
        )
        service.refresh_publications(["mart_spend_by_weekday_hour"])
        client = TestClient(
            create_app(
                AccountTransactionService(
                    landing_root=Path(temp_dir) / "landing",
                    metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
                ),
                transformation_service=service,
            )
        )
        response = client.get("/reports/spend-heatmap")
        assert response.status_code == 200
        body = response.json()
        assert body["window_days"] == 28
        assert body["window_end"] == "2026-03-04"
        assert body["cells"][0][18] == "42.00"
        assert body["untimed"][2] == "60.00"
        assert body["coverage"] == "mixed"
        assert body["publications"] == ["mart_spend_by_weekday_hour"]

        rewound = client.get(
            "/reports/spend-heatmap", params={"window": 1, "as_of": "2026-03-02"}
        ).json()
        assert rewound["window_start"] == "2026-03-02"
        assert rewound["untimed"][2] == "0.00"
        assert rewound["cells"][0][18] == "42.00"

        assert client.get("/reports/spend-heatmap", params={"window": 0}).status_code == 400
        assert client.get("/reports/spend-heatmap", params={"window": 400}).status_code == 400

        bare_client = TestClient(
            create_app(
                AccountTransactionService(
                    landing_root=Path(temp_dir) / "landing2",
                    metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs2.db"),
                )
            )
        )
        assert bare_client.get("/reports/spend-heatmap").status_code == 404
