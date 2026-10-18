"""Durable action-proposal queue: migrations, store parity and API behaviour.

- sqlite 0009 / postgres 0016 create the queue and its append-only history,
  and the SQLite inline bootstrap matches the migration
- every store (in-memory, SQLite) passes the same lifecycle contract; the
  Postgres run lives in ``test_control_plane_store_contract.py``
- the API persists proposals across an app restart, records the
  authenticated principal, and answers idempotency / reopen conflicts with 409
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.domains.finance.pipelines.account_transaction_service import (
    AccountTransactionService,
)
from packages.pipelines.transformation_service import TransformationService
from packages.platform.action_proposals import (
    ActionProposalRegistry,
    InMemoryActionProposalStore,
    build_action_proposal_registry,
)
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.migration_runner import apply_pending_sqlite_migrations
from packages.storage.run_metadata import RunMetadataRepository
from tests.control_plane_test_support import (
    assert_action_proposal_resolution_is_exclusive,
    assert_action_proposal_store_behaviour,
)

ROOT = Path(__file__).resolve().parents[1]
SQLITE_MIGRATION = ROOT / "migrations/sqlite/0009_action_proposal_queue.sql"
POSTGRES_MIGRATION = ROOT / "migrations/postgres/0016_action_proposal_queue.sql"


def _table_columns(sql: str) -> dict[str, list[str]]:
    tables: dict[str, list[str]] = {}
    for match in re.finditer(
        r"CREATE TABLE IF NOT EXISTS (\w+) \((.*?)\n\s*\);", sql, flags=re.DOTALL
    ):
        columns = []
        for line in match.group(2).splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith(("UNIQUE", "--")):
                columns.append(stripped.split()[0])
        tables[match.group(1)] = columns
    return tables


def test_sqlite_migration_0009_creates_queue_tables() -> None:
    conn = sqlite3.connect(":memory:")
    applied = apply_pending_sqlite_migrations(conn, ROOT / "migrations" / "sqlite")
    assert "0009_action_proposal_queue" in applied
    tables = {
        row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"action_proposals", "action_proposal_events"} <= tables
    assert "0009_action_proposal_queue" not in apply_pending_sqlite_migrations(
        conn, ROOT / "migrations" / "sqlite"
    )


def test_postgres_migration_mirrors_sqlite_and_has_no_duplicate_columns() -> None:
    sqlite_tables = _table_columns(SQLITE_MIGRATION.read_text())
    postgres_tables = _table_columns(POSTGRES_MIGRATION.read_text())
    assert set(sqlite_tables) == {"action_proposals", "action_proposal_events"}
    assert sqlite_tables == postgres_tables
    for columns in sqlite_tables.values():
        assert len(columns) == len(set(columns))
    assert "ALTER TABLE" not in SQLITE_MIGRATION.read_text()
    assert "ALTER TABLE" not in POSTGRES_MIGRATION.read_text()
    # Timestamps are aware in Postgres, matching the aware-UTC ISO text in SQLite.
    assert "created_at TIMESTAMPTZ NOT NULL" in POSTGRES_MIGRATION.read_text()
    assert "occurred_at TIMESTAMPTZ NOT NULL" in POSTGRES_MIGRATION.read_text()


def test_sqlite_inline_bootstrap_matches_migration_columns() -> None:
    with TemporaryDirectory() as tmp:
        IngestionConfigRepository(Path(tmp) / "config.db")
        conn = sqlite3.connect(Path(tmp) / "config.db")
        for table, columns in _table_columns(SQLITE_MIGRATION.read_text()).items():
            bootstrapped = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
            assert bootstrapped == columns


def test_in_memory_store_passes_the_store_contract() -> None:
    store = InMemoryActionProposalStore()
    assert_action_proposal_store_behaviour(store)
    assert_action_proposal_resolution_is_exclusive(InMemoryActionProposalStore())
    assert ActionProposalRegistry(store=store).durable is False


def test_registry_builder_prefers_control_plane_store() -> None:
    with TemporaryDirectory() as tmp:
        repository = IngestionConfigRepository(Path(tmp) / "config.db")
        assert build_action_proposal_registry(repository).durable is True
    assert build_action_proposal_registry(None).durable is False
    assert build_action_proposal_registry(object()).durable is False


def test_history_rows_are_append_only() -> None:
    with TemporaryDirectory() as tmp:
        repository = IngestionConfigRepository(Path(tmp) / "config.db")
        registry = ActionProposalRegistry(store=repository)
        proposal = registry.register(
            policy_id="p",
            policy_name="P",
            verdict="notify",
            value="1",
            notification_id=None,
            created_by="agent",
        )
        registry.register(
            policy_id="p",
            policy_name="P",
            verdict="notify",
            value="2",
            notification_id=None,
            action_id=proposal.action_id,
            created_by="agent",
        )
        registry.dismiss(proposal.action_id, resolved_by="operator")
        conn = sqlite3.connect(Path(tmp) / "config.db")
        rows = conn.execute(
            "SELECT sequence, kind, actor FROM action_proposal_events"
            " WHERE action_id = ? ORDER BY sequence",
            (proposal.action_id,),
        ).fetchall()
        assert rows == [(1, "drafted", "agent"), (2, "refreshed", "agent"), (3, "dismissed", "operator")]
    # The store port exposes no way to edit or delete history.
    assert not any(
        name.startswith(("delete", "remove")) or "event" in name
        for name in dir(InMemoryActionProposalStore)
        if not name.startswith("_")
    )


def _app(tmp: str) -> TestClient:
    service = AccountTransactionService(
        landing_root=Path(tmp) / "landing",
        metadata_repository=RunMetadataRepository(Path(tmp) / "runs.db"),
    )
    repository = IngestionConfigRepository(Path(tmp) / "config.db")
    return TestClient(
        create_app(
            service,
            config_repository=repository,
            transformation_service=TransformationService(DuckDBStore.memory()),
        )
    )


_BODY = {
    "policy_id": "mcp:propose_action",
    "policy_name": "Agent drafted: lower office heating",
    "verdict": "notify",
    "value": "19.5",
    "created_by": "agent-a",
}


def test_queue_survives_an_api_restart() -> None:
    with TemporaryDirectory() as tmp:
        first = _app(tmp)
        drafted = first.post(
            "/api/actions/proposals",
            json={**_BODY, "provenance": {"publication_keys": ["monthly_cashflow"]}},
        )
        assert drafted.status_code == 200
        action_id = drafted.json()["action_id"]
        stamped = drafted.json()["provenance"]
        assert stamped["trust_source"] == "server_stamped"
        dismissed = first.post(
            f"/api/actions/proposals/{action_id}/dismiss", json={"reason": "not now"}
        )
        assert dismissed.status_code == 200

        restarted = _app(tmp)
        detail = restarted.get(f"/api/actions/proposals/{action_id}")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["status"] == "dismissed"
        assert payload["resolution_reason"] == "not now"
        assert payload["provenance"] == stamped
        assert [event["kind"] for event in payload["history"]] == ["drafted", "dismissed"]
        # The resolution guard holds across the restart too.
        again = restarted.post(f"/api/actions/proposals/{action_id}/approve")
        assert again.status_code == 409
        ha_view = restarted.get("/api/ha/actions/proposals").json()["proposals"]
        assert [row["action_id"] for row in ha_view] == [action_id]


def test_idempotency_key_replays_and_conflicts_over_the_api() -> None:
    with TemporaryDirectory() as tmp:
        client = _app(tmp)
        body = {**_BODY, "idempotency_key": "office-heat-2026-10"}
        first = client.post("/api/actions/proposals", json=body)
        assert first.status_code == 200
        assert first.json()["action_id"] == "agent_office-heat-2026-10"
        assert first.json()["idempotency_key"] == "office-heat-2026-10"
        replay = client.post("/api/actions/proposals", json={**body, "value": "19.0"})
        assert replay.status_code == 200
        assert replay.json()["value"] == "19.0"
        assert len(client.get("/api/actions/proposals").json()["proposals"]) == 1

        foreign = client.post(
            "/api/actions/proposals", json={**body, "created_by": "agent-b"}
        )
        assert foreign.status_code == 409

        action_id = first.json()["action_id"]
        assert client.post(f"/api/actions/proposals/{action_id}/approve").status_code == 200
        after = client.post("/api/actions/proposals", json={**body, "value": "18.0"})
        assert after.status_code == 200
        assert after.json()["status"] == "approved"
        assert after.json()["value"] == "19.0"

        bad_key = client.post(
            "/api/actions/proposals", json={**_BODY, "idempotency_key": "no spaces!"}
        )
        assert bad_key.status_code == 422


def test_drafting_over_a_resolved_action_id_is_a_conflict() -> None:
    with TemporaryDirectory() as tmp:
        client = _app(tmp)
        for prefix in ("/api/actions/proposals", "/api/ha/actions/proposals"):
            action_id = f"fixed-{prefix.count('/')}"
            body = {**_BODY, "action_id": action_id}
            assert client.post(prefix, json=body).status_code == 200
            assert client.post(f"{prefix}/{action_id}/approve").status_code == 200
            reopened = client.post(prefix, json=body)
            assert reopened.status_code == 409
            assert "already approved" in reopened.json()["detail"]
            assert client.get(f"/api/actions/proposals/{action_id}").json()["status"] == (
                "approved"
            )


def test_proposer_supplied_trust_is_labelled_when_no_lookup_exists() -> None:
    registry = ActionProposalRegistry()
    service_tmp = TemporaryDirectory()
    with service_tmp as tmp:
        service = AccountTransactionService(
            landing_root=Path(tmp) / "landing",
            metadata_repository=RunMetadataRepository(Path(tmp) / "runs.db"),
        )
        app = create_app(
            service,
            transformation_service=TransformationService(DuckDBStore.memory()),
            ha_action_proposal_registry=registry,
        )
        client = TestClient(app)
        drafted = client.post(
            "/api/actions/proposals",
            json={
                **_BODY,
                "provenance": {
                    "publication_keys": [],
                    "confidence_verdict_at_draft": "trustworthy",
                },
            },
        )
        assert drafted.status_code == 200
        provenance = drafted.json()["provenance"]
        assert provenance["trust_source"] == "proposer_supplied"
        assert provenance["confidence_verdict_at_draft"] == "trustworthy"
