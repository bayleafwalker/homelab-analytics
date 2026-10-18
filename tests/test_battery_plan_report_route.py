"""/reports/battery-plan-outcome serves the reporting marts with disclosures."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from apps.api.app import create_app
from apps.api.auth_policies import API_ROUTE_AUTHORIZATION_LOOKUP
from packages.domains.finance.pipelines.account_transaction_service import (
    AccountTransactionService,
)
from packages.platform.auth.contracts import UserRole
from packages.storage.run_metadata import RunMetadataRepository
from tests.test_battery_plan_outcome import _service, _store_with_history


def test_battery_plan_outcome_route_returns_verdict_values_and_decision() -> None:
    store, assessed_at = _store_with_history()
    transformation_service = _service(store, assessed_at=assessed_at)
    transformation_service.refresh_battery_plan_outcome()
    with TemporaryDirectory() as temp_dir:
        service = AccountTransactionService(
            landing_root=Path(temp_dir) / "landing",
            metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
        )
        client = TestClient(create_app(service, transformation_service=transformation_service))

        response = client.get("/reports/battery-plan-outcome")
        assert response.status_code == 200
        payload = response.json()
        [row] = payload["rows"]
        assert row["verdict"] == "no_benefit_estimated"
        assert row["actuation_authorized"] is False
        assert payload["decision"]["decision_key"] == "kotiakku_battery_plan_review"
        assert payload["publication_keys"] == [
            "mart_battery_plan_outcome",
            "mart_battery_plan_outcome_values",
        ]
        statuses = {value["value_key"]: value["value_status"] for value in payload["values"]}
        assert statuses["estimated_savings_eur"] == "estimated"
        missing = {value["value_key"]: value["is_missing"] for value in payload["values"]}
        assert missing["net_site_cost_eur"] is True

        filtered = client.get("/reports/battery-plan-outcome", params={"decision_month": "2025-12"})
        assert filtered.status_code == 200
        assert filtered.json()["rows"] == []
        assert filtered.json()["values"] == []


def test_battery_plan_outcome_route_is_reader_accessible_report() -> None:
    assert (
        API_ROUTE_AUTHORIZATION_LOOKUP.required_role_for_path("/reports/battery-plan-outcome")
        == UserRole.READER
    )
