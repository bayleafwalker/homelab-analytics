"""Unit and HTTP coverage for the seven-day operating horizon merge."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from control_plane_test_support import seed_source_asset_graph
from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.application.use_cases.operating_horizon import build_operating_horizon
from packages.domains.finance.pipelines.account_transaction_service import (
    AccountTransactionService,
)
from packages.pipelines.reporting_service import ReportingService
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.run_metadata import RunMetadataRepository


def _view(source_asset_id: str, name: str, expected: datetime | None):
    return SimpleNamespace(
        source_asset_id=source_asset_id,
        dataset_name=f"{source_asset_id}_dataset",
        name=name,
        next_expected_at=expected,
        suggested_action="upload_missing_period",
    )


def _config(source_asset_id: str, mode: str, human: bool):
    return SimpleNamespace(
        source_asset_id=source_asset_id,
        acquisition_mode=mode,
        requires_human_action=human,
    )


def test_merge_keeps_kinds_identity_and_amounts_within_the_window():
    today = date(2026, 11, 22)
    day_six = today + timedelta(days=6)
    rows = build_operating_horizon(
        start_date=today,
        fixed_costs=[
            {
                "contract_name": "Power bill",
                "expected_date": today,
                "expected_amount": "42.00",
                "currency": "EUR",
            },
            {
                "contract_name": "Water bill",
                "expected_date": day_six,
                "expected_amount": "23.00",
                "currency": "EUR",
            },
            {"contract_name": "Beyond horizon", "expected_date": today + timedelta(days=7)},
            {"contract_name": "Undated cost", "expected_date": None},
        ],
        contract_renewals=[
            {
                "contract_id": "renew-1",
                "contract_name": "Energy renewal",
                "renewal_date": today,
                "current_price": "18.00",
                "currency": "EUR",
            },
            {
                "contract_id": "renew-old",
                "contract_name": "Expired renewal",
                "renewal_date": today - timedelta(days=1),
            },
        ],
        freshness_views=[
            _view("manual", "Manual export", datetime.combine(today, datetime.min.time())),
            _view("auto", "Automatic pull", datetime.combine(today, datetime.min.time())),
            _view("undated", "Undated export", None),
        ],
        freshness_configs=[
            _config("manual", "manual_export", True),
            _config("auto", "api_pull", False),
            _config("undated", "manual_export", True),
        ],
        pending_proposals=[
            SimpleNamespace(action_id="approval-1", policy_name="Approve thermostat"),
            SimpleNamespace(action_id="approval-2", policy_name="Approve thermostat"),
        ],
    )

    merged = rows["rows"]
    assert rows["start_date"] == today.isoformat()
    assert [row["date"] for row in merged] == [today.isoformat()] * 5 + [day_six.isoformat()]
    assert {(row["kind"], row["label"]) for row in merged} == {
        ("approval", "Approve thermostat"),
        ("export", "Manual export"),
        ("fixed_cost", "Power bill"),
        ("fixed_cost", "Water bill"),
        ("renewal", "Energy renewal"),
    }
    assert len({row["id"] for row in merged}) == len(merged)
    assert "Expired renewal" not in {row["label"] for row in merged}
    assert "Automatic pull" not in {row["label"] for row in merged}
    assert "Undated export" not in {row["label"] for row in merged}
    assert "Beyond horizon" not in {row["label"] for row in merged}

    power = next(row for row in merged if row["label"] == "Power bill")
    assert (power["amount"], power["currency"]) == ("42.00", "EUR")
    approval = next(row for row in merged if row["kind"] == "approval")
    assert approval["date"] == today.isoformat()
    assert approval["actionable_now"] is True
    assert "deadline" not in approval


def test_empty_merge_still_reports_the_api_date_boundary():
    today = date(2026, 11, 22)
    assert build_operating_horizon(start_date=today) == {
        "start_date": today.isoformat(),
        "rows": [],
    }


def _client(tmp_path: Path, *, reporting):
    service = AccountTransactionService(
        landing_root=tmp_path / "landing",
        metadata_repository=RunMetadataRepository(tmp_path / "runs.db"),
    )
    config = IngestionConfigRepository(tmp_path / "config.db")
    seed_source_asset_graph(config)
    return TestClient(
        create_app(
            service,
            config_repository=config,
            reporting_service=reporting,
            enable_unsafe_admin=True,
        )
    )


def test_unavailable_feed_is_not_reported_as_an_empty_horizon(tmp_path, monkeypatch):
    reporting = ReportingService(TransformationService(DuckDBStore.memory()))

    def fail():
        raise RuntimeError("mart unavailable")

    monkeypatch.setattr(reporting, "get_upcoming_fixed_costs_30d", fail)
    with _client(tmp_path, reporting=reporting) as client:
        response = client.get("/control/operating-horizon")
    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"].lower()


def test_missing_reporting_service_reports_the_feed_as_unavailable(tmp_path):
    service = AccountTransactionService(
        landing_root=tmp_path / "landing",
        metadata_repository=RunMetadataRepository(tmp_path / "runs.db"),
    )
    config = IngestionConfigRepository(tmp_path / "config.db")
    with TestClient(
        create_app(
            service,
            config_repository=config,
            enable_unsafe_admin=True,
        )
    ) as client:
        response = client.get("/control/operating-horizon")
    assert response.status_code == 503
    assert response.json()["detail"].startswith("Operating horizon is unavailable")
