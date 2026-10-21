"""Decision ledger: migrations, permissions, use-case rules and API routes."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest
from fastapi.testclient import TestClient

from apps.api.app import create_app
from apps.api.auth_policies import API_ROUTE_AUTHORIZATION_LOOKUP
from packages.application.use_cases.decision_ledger import actor_from_principal
from packages.domains.finance.pipelines.account_transaction_service import (
    AccountTransactionService,
)
from packages.domains.utilities.pipelines.battery_plan_outcome import get_battery_plan_outcome
from packages.domains.utilities.pipelines.publication_refresh import (
    refresh_battery_plan_publication,
)
from packages.platform.auth.contracts import UserRole
from packages.platform.auth.permission_registry import (
    KNOWN_PERMISSIONS,
    PERMISSION_CONTROL_DECISIONS_READ,
    PERMISSION_CONTROL_DECISIONS_WRITE,
    permissions_for_role,
    permissions_for_service_token_scopes,
)
from packages.platform.auth.role_hierarchy import AuthenticatedPrincipal
from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.migration_runner import apply_pending_sqlite_migrations
from packages.storage.run_metadata import RunMetadataRepository
from tests.test_battery_plan_outcome import _service, _store_with_history

ROOT = Path(__file__).resolve().parents[1]


def test_sqlite_migration_0008_creates_decision_ledger_tables() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    applied = apply_pending_sqlite_migrations(conn, ROOT / "migrations" / "sqlite")
    assert "0008_decision_ledger" in applied
    tables = {
        row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"decision_records", "decision_follow_ups"} <= tables
    again = apply_pending_sqlite_migrations(conn, ROOT / "migrations" / "sqlite")
    assert "0008_decision_ledger" not in again


def test_postgres_migration_mirrors_sqlite_columns() -> None:
    sqlite_sql = (ROOT / "migrations/sqlite/0008_decision_ledger.sql").read_text()
    postgres_sql = (ROOT / "migrations/postgres/0015_decision_ledger.sql").read_text()

    def columns(sql: str) -> list[str]:
        names = []
        for line in sql.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith(("--", "CREATE", "ON ", ")")):
                names.append(stripped.split()[0])
        return names

    assert columns(sqlite_sql) == columns(postgres_sql)
    for name in set(columns(sqlite_sql)):
        assert columns(sqlite_sql).count(name) <= 2  # once per table at most


def test_decision_permissions_are_role_bound_and_not_service_writable() -> None:
    assert {PERMISSION_CONTROL_DECISIONS_READ, PERMISSION_CONTROL_DECISIONS_WRITE} <= KNOWN_PERMISSIONS
    reader = permissions_for_role(UserRole.READER)
    operator = permissions_for_role(UserRole.OPERATOR)
    admin = permissions_for_role(UserRole.ADMIN)
    assert PERMISSION_CONTROL_DECISIONS_READ in reader
    assert PERMISSION_CONTROL_DECISIONS_WRITE not in reader
    assert PERMISSION_CONTROL_DECISIONS_WRITE in operator
    assert PERMISSION_CONTROL_DECISIONS_WRITE in admin
    all_scopes = ("reports:read", "runs:read", "ingest:write", "ha-bridge:ingest", "admin:write")
    assert PERMISSION_CONTROL_DECISIONS_WRITE not in permissions_for_service_token_scopes(all_scopes)


@pytest.mark.parametrize(
    "method,path,role,permission",
    [
        ("GET", "/control/decisions", UserRole.READER, PERMISSION_CONTROL_DECISIONS_READ),
        ("GET", "/control/decisions/definitions", UserRole.READER, PERMISSION_CONTROL_DECISIONS_READ),
        ("GET", "/control/decisions/dec_1", UserRole.READER, PERMISSION_CONTROL_DECISIONS_READ),
        ("POST", "/control/decisions", UserRole.OPERATOR, PERMISSION_CONTROL_DECISIONS_WRITE),
        (
            "POST",
            "/control/decisions/dec_1/follow-ups",
            UserRole.OPERATOR,
            PERMISSION_CONTROL_DECISIONS_WRITE,
        ),
    ],
)
def test_decision_route_policies(
    method: str, path: str, role: UserRole, permission: str
) -> None:
    lookup = API_ROUTE_AUTHORIZATION_LOOKUP
    assert lookup.required_role_for_request(path, method=method) == role
    assert lookup.required_permission_for_request(path, method=method) == permission


def test_actor_reflects_auth_identity_or_its_absence() -> None:
    disabled = actor_from_principal(None)
    assert disabled.actor_authenticated is False
    assert disabled.actor_auth_provider == "disabled"
    principal = AuthenticatedPrincipal(
        user_id="u1",
        username="household-operator",
        role=UserRole.OPERATOR,
        auth_provider="oidc",
    )
    actor = actor_from_principal(principal)
    assert actor.actor == "household-operator"
    assert actor.actor_role == "operator"
    assert actor.actor_authenticated is True


def _client(temp_dir: str, **history: Any) -> tuple[TestClient, dict[str, Any]]:
    store, assessed_at = _store_with_history(**history)
    transformation = _service(store, assessed_at=assessed_at)
    refresh_battery_plan_publication(transformation)
    [row] = get_battery_plan_outcome(transformation.store)
    service = AccountTransactionService(
        landing_root=Path(temp_dir) / "landing",
        metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
    )
    app = create_app(
        service,
        config_repository=IngestionConfigRepository(Path(temp_dir) / "config.db"),
        transformation_service=transformation,
    )
    return TestClient(app), row


def _decision_body(row: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "decision_key": "kotiakku_battery_plan_review",
        "subject_period": "2026-01",
        "subject_row_ref": row["assessment_id"],
        "outcome": "review_battery_plan",
        "rationale": "Estimated savings stay below the monthly battery cost.",
        "uncertainty": "Single winter month.",
    }
    body.update(overrides)
    return body


def test_record_decision_links_exact_publication_and_lineage_then_follow_up() -> None:
    with TemporaryDirectory() as temp_dir:
        client, row = _client(temp_dir)

        definitions = client.get("/control/decisions/definitions").json()["definitions"]
        assert definitions[0]["decision_key"] == "kotiakku_battery_plan_review"

        created = client.post("/control/decisions", json=_decision_body(row))
        assert created.status_code == 201, created.text
        decision = created.json()["decision"]
        assert decision["subject"] == {
            "publication_key": "mart_battery_plan_outcome",
            "schema_version": "1.0.0",
            "period": "2026-01",
            "row_ref": row["assessment_id"],
            "verdict": "no_benefit_estimated",
        }
        assert decision["decision_version"] == "1.1.0"
        assert decision["lineage_reference"]["source_run_ids"] == [
            "synthetic-economics-run",
            "synthetic-measurement-run",
        ]
        assert decision["lineage_reference"]["source_layer"] == "transformation.fact_ha_state_change"
        assert decision["evidence_snapshot"]["outcome"]["assessment_id"] == row["assessment_id"]
        assert decision["evidence_snapshot"]["values"]
        assert decision["actor"]["authenticated"] is False
        assert decision["actuation_authorized"] is False
        assert decision["status"] == "awaiting_follow_up"
        assert decision["is_non_decision"] is False

        decision_id = decision["decision_id"]
        follow_up = client.post(
            f"/control/decisions/{decision_id}/follow-ups",
            json={
                "observed_at": datetime.now(UTC).isoformat(),
                "observation_period": "2026-02",
                "realized_result": "Contract terms reviewed; battery plan kept pending quote.",
                "realized_value_eur": "41.20",
                "realized_value_status": "observed",
                "evidence_effect": "confirmed_decision",
            },
        )
        assert follow_up.status_code == 201, follow_up.text
        assert follow_up.json()["follow_up"]["realized_value_status"] == "observed"

        fetched = client.get(f"/control/decisions/{decision_id}").json()["decision"]
        assert fetched["status"] == "followed_up"
        assert Decimal(fetched["follow_ups"][0]["realized_value_eur"]) == Decimal("41.20")
        # The projected estimate and the realized value stay distinct.
        assert fetched["evidence_snapshot"]["outcome"]["verdict"] == "no_benefit_estimated"

        listed = client.get("/control/decisions", params={"subject_period": "2026-01"})
        assert [item["decision_id"] for item in listed.json()["decisions"]] == [decision_id]


def test_insufficient_evidence_requires_acknowledged_gaps_and_allows_non_decision() -> None:
    with TemporaryDirectory() as temp_dir:
        client, row = _client(temp_dir, skipped_windows=1)
        assert row["verdict"] == "insufficient_evidence"

        refused = client.post(
            "/control/decisions",
            json=_decision_body(row, outcome="defer_pending_evidence"),
        )
        assert refused.status_code == 422
        assert "acknowledge the evidence gaps" in refused.json()["detail"]

        recorded = client.post(
            "/control/decisions",
            json=_decision_body(
                row,
                outcome="defer_pending_evidence",
                rationale="Coverage gap; wait for backfill.",
                evidence_gaps_acknowledged=["measurement_window_coverage_incomplete"],
            ),
        )
        assert recorded.status_code == 201, recorded.text
        decision = recorded.json()["decision"]
        assert decision["is_non_decision"] is True
        assert decision["evidence_gaps_acknowledged"] == [
            "measurement_window_coverage_incomplete"
        ]

        preserved = client.post(
            f"/control/decisions/{decision['decision_id']}/follow-ups",
            json={
                "observed_at": datetime.now(UTC).isoformat(),
                "realized_result": "Backfill still missing; non-decision stands.",
                "evidence_effect": "preserved_non_decision",
            },
        )
        assert preserved.status_code == 201, preserved.text


def test_decision_requests_are_validated() -> None:
    with TemporaryDirectory() as temp_dir:
        client, row = _client(temp_dir)
        cases = [
            (_decision_body(row, decision_key="unknown"), 404),
            (_decision_body(row, subject_period="2025-11"), 404),
            (_decision_body(row, subject_row_ref="bpo_stale"), 409),
            (_decision_body(row, outcome="charge_battery_now"), 422),
            (_decision_body(row, rationale="  "), 422),
            (_decision_body(row, follow_up_due_on="2020-01-01"), 422),
            (_decision_body(row, actuate=True), 422),
        ]
        for body, status in cases:
            response = client.post("/control/decisions", json=body)
            assert response.status_code == status, (body, response.text)

        decision_id = client.post("/control/decisions", json=_decision_body(row)).json()[
            "decision"
        ]["decision_id"]
        now = datetime.now(UTC)
        bad_follow_ups = [
            {"observed_at": now.isoformat(), "realized_result": "x", "evidence_effect": "nope"},
            {
                "observed_at": now.isoformat(),
                "realized_result": "x",
                "evidence_effect": "preserved_non_decision",
            },
            {
                "observed_at": (now + timedelta(days=2)).isoformat(),
                "realized_result": "x",
                "evidence_effect": "inconclusive",
            },
            {
                "observed_at": now.replace(tzinfo=None).isoformat(),
                "realized_result": "x",
                "evidence_effect": "inconclusive",
            },
            {
                "observed_at": now.isoformat(),
                "realized_result": "x",
                "evidence_effect": "inconclusive",
                "realized_value_eur": "10",
            },
        ]
        for body in bad_follow_ups:
            response = client.post(f"/control/decisions/{decision_id}/follow-ups", json=body)
            assert response.status_code == 422, (body, response.text)
        missing = client.post(
            "/control/decisions/dec_missing/follow-ups",
            json={"observed_at": now.isoformat(), "realized_result": "x", "evidence_effect": "inconclusive"},
        )
        assert missing.status_code == 404
        assert client.get("/control/decisions/dec_missing").status_code == 404


def test_decision_routes_expose_no_actuation_surface() -> None:
    source = (ROOT / "apps/api/routes/decision_routes.py").read_text()
    for token in ("call_service", "/api/services", "ha_bridge", "mqtt", "HA_TOKEN"):
        assert token not in source
