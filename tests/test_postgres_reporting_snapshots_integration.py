"""As-of snapshots on the Postgres-published reporting path."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from packages.pipelines.reporting_service import ReportingAccessMode, ReportingService
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.postgres_reporting import PostgresReportingStore
from tests.postgres_test_support import running_postgres_container
from tests.test_reporting_publication_snapshots import _capture, _load_month

pytestmark = [pytest.mark.integration, pytest.mark.slow]


def test_published_mode_reads_snapshots_from_postgres_with_retention() -> None:
    ts = TransformationService(DuckDBStore.memory())
    with running_postgres_container() as dsn:
        store = PostgresReportingStore(dsn)
        writer = ReportingService(ts, publication_store=store, snapshot_retention_months=2)
        for index, month in enumerate(("2026-01", "2026-02", "2026-03"), start=1):
            _load_month(ts, month, run_id=f"run-{month}")
            _capture(writer, run_id=f"run-{month}", at=datetime(2026, index + 1, 1, tzinfo=UTC))
        # Same-month refresh replaces the March snapshot in one transaction.
        _capture(writer, run_id="run-2026-03-b", at=datetime(2026, 4, 9, tzinfo=UTC))

        reader = ReportingService(
            ts,
            publication_store=store,
            access_mode=ReportingAccessMode.PUBLISHED,
        )
        assert reader.list_publication_snapshot_months("mart_household_overview") == [
            "2026-02",
            "2026-03",
        ]
        march = reader.get_publication_snapshot("mart_household_overview", "2026-03")
        assert march is not None
        assert march.run_id == "run-2026-03-b"
        assert march.captured_at == "2026-04-09T00:00:00+00:00"
        assert march.rows[0]["current_month"] == "2026-03"
        assert reader.get_publication_snapshot("mart_household_overview", "2026-01") is None
        rows = store.fetchall_dicts(
            "SELECT COUNT(*) AS n FROM reporting_publication_snapshot "
            "WHERE publication_key = %s AND reference_month = %s",
            ["mart_household_overview", "2026-03"],
        )
        assert rows[0]["n"] == 1
