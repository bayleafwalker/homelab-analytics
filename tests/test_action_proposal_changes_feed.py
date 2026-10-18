"""The approval-queue changes feed: migrations, bootstrap upgrade and API.

- sqlite 0013 / postgres 0020 add a commit-ordered ``feed_position`` to every
  history event and backfill existing events; the SQLite inline bootstrap
  upgrades an existing database the same way
- ``GET /api/actions/proposals/changes`` serves a strict ``resource-changes/v1``
  page (the shape vuoro's client validates with ``extra="forbid"``), pages by
  opaque cursor, narrows to one proposal, and rejects foreign cursors
The store-level ordering contract (concurrent writers, every event once) is
``assert_action_proposal_changes_feed`` in ``control_plane_test_support``,
run against the in-memory, SQLite and Postgres stores.
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Literal

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field

from apps.api.app import create_app
from packages.application.use_cases.action_proposal_changes import (
    InvalidCursorError,
    decode_cursor,
    encode_cursor,
)
from packages.domains.finance.pipelines.account_transaction_service import (
    AccountTransactionService,
)
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.migration_runner import apply_pending_sqlite_migrations
from packages.storage.run_metadata import RunMetadataRepository

ROOT = Path(__file__).resolve().parents[1]
SQLITE_DIR = ROOT / "migrations" / "sqlite"
SQLITE_MIGRATION = SQLITE_DIR / "0013_action_proposal_changes_feed.sql"
POSTGRES_MIGRATION = ROOT / "migrations/postgres/0020_action_proposal_changes_feed.sql"


# A local mirror of vuoro-client's strict observation envelopes
# (vuoro_client.resources.ResourceChanges / ResourceEvent).
class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _ResourceEvent(_Strict):
    event_id: str = Field(min_length=1)
    terminal: bool
    data: dict[str, Any]


class _ResourceChanges(_Strict):
    schema_version: Literal["resource-changes/v1"]
    reference: str = Field(min_length=1)
    next_cursor: str = Field(min_length=1)
    events: list[_ResourceEvent]


def _insert_legacy_events(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO action_proposals (action_id, policy_id, policy_name, verdict,"
        " notification_id, adapter, source_kind, status, created_at, metadata_json,"
        " updated_at) VALUES ('a1', 'p', 'P', 'notify', 'a1', 'platform', 'agent',"
        " 'dismissed', '2026-10-01T00:00:00+00:00', '{}', '2026-10-01T00:00:00+00:00')"
    )
    for sequence, kind, at in (
        (2, "dismissed", "2026-10-01T00:05:00+00:00"),
        (1, "drafted", "2026-10-01T00:00:00+00:00"),
    ):
        conn.execute(
            "INSERT INTO action_proposal_events (event_id, action_id, sequence, kind,"
            " occurred_at) VALUES (?, 'a1', ?, ?, ?)",
            (f"ape_legacy_{sequence}", sequence, kind, at),
        )
    conn.commit()


def test_sqlite_migration_0013_backfills_feed_positions_in_order() -> None:
    with TemporaryDirectory() as tmp:
        before = Path(tmp) / "before"
        before.mkdir()
        for migration in sorted(SQLITE_DIR.glob("*.sql")):
            if migration.name < SQLITE_MIGRATION.name:
                shutil.copy(migration, before / migration.name)
        conn = sqlite3.connect(":memory:")
        apply_pending_sqlite_migrations(conn, before)
        _insert_legacy_events(conn)

        applied = apply_pending_sqlite_migrations(conn, SQLITE_DIR)
        assert SQLITE_MIGRATION.stem in applied
        rows = conn.execute(
            "SELECT sequence, feed_position FROM action_proposal_events ORDER BY feed_position"
        ).fetchall()
        assert rows == [(1, 1), (2, 2)]
        assert conn.execute(
            "SELECT last_position FROM action_proposal_feed_counter"
        ).fetchall() == [(2,)]
        assert SQLITE_MIGRATION.stem not in apply_pending_sqlite_migrations(conn, SQLITE_DIR)


def test_postgres_migration_mirrors_sqlite_feed_schema() -> None:
    sqlite_sql = SQLITE_MIGRATION.read_text()
    postgres_sql = POSTGRES_MIGRATION.read_text()
    for sql in (sqlite_sql, postgres_sql):
        assert sql.count("ADD COLUMN") == 1
        assert "ADD COLUMN" in sql and "feed_position" in sql
        assert "CREATE TABLE IF NOT EXISTS action_proposal_feed_counter" in sql
        assert "idx_action_proposal_events_feed_position" in sql
        assert "ROW_NUMBER() OVER (ORDER BY occurred_at, action_id, sequence)" in sql
    assert "feed_position BIGINT" in postgres_sql
    assert "SET NOT NULL" in postgres_sql


def test_inline_bootstrap_upgrades_an_existing_database() -> None:
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.db"
        IngestionConfigRepository(path)
        conn = sqlite3.connect(path)
        # Recreate the pre-feed shape: no position column, no counter.
        conn.execute("DROP INDEX idx_action_proposal_events_feed_position")
        conn.execute("ALTER TABLE action_proposal_events DROP COLUMN feed_position")
        conn.execute("DROP TABLE action_proposal_feed_counter")
        _insert_legacy_events(conn)
        conn.close()

        repository = IngestionConfigRepository(path)
        changes = repository.list_action_proposal_changes(after_position=0, limit=10)
        assert [(item.sequence, item.position) for item in changes] == [(1, 1), (2, 2)]
        # New events continue after the backfilled ones.
        from packages.platform.action_proposals import ActionProposalRegistry

        registry = ActionProposalRegistry(store=repository)
        registry.register(
            policy_id="p2",
            policy_name="P2",
            verdict="notify",
            value=None,
            notification_id=None,
            created_by="agent",
        )
        assert [item.position for item in registry.list_changes(after_position=2)] == [3]


def test_cursor_round_trip_and_rejection() -> None:
    assert decode_cursor(None) == 0
    assert decode_cursor("") == 0
    assert decode_cursor(encode_cursor(42)) == 42
    for bad in ("42", "apf.-1", "apf.01", "apf.x", "ape.1"):
        try:
            decode_cursor(bad)
        except InvalidCursorError:
            continue
        raise AssertionError(f"accepted {bad!r}")


def _client(tmp: str) -> TestClient:
    service = AccountTransactionService(
        landing_root=Path(tmp) / "landing",
        metadata_repository=RunMetadataRepository(Path(tmp) / "runs.db"),
    )
    return TestClient(
        create_app(
            service,
            config_repository=IngestionConfigRepository(Path(tmp) / "config.db"),
            transformation_service=TransformationService(DuckDBStore.memory()),
        )
    )


def _draft(client: TestClient, title: str) -> str:
    response = client.post(
        "/api/actions/proposals",
        json={
            "policy_id": "mcp:propose_action",
            "policy_name": title,
            "verdict": "notify",
            "value": "1",
            "adapter": "platform",
            "source_kind": "agent",
            "created_by": "agent-a",
        },
    )
    assert response.status_code == 200
    return str(response.json()["action_id"])


def test_changes_feed_api_pages_by_cursor_in_strict_resource_changes_shape() -> None:
    with TemporaryDirectory() as tmp:
        client = _client(tmp)
        empty = client.get("/api/actions/proposals/changes")
        assert empty.status_code == 200
        assert _ResourceChanges.model_validate(empty.json()).model_dump() == {
            "schema_version": "resource-changes/v1",
            "reference": "action-proposals",
            "next_cursor": "apf.0",
            "events": [],
        }

        first = _draft(client, "First")
        second = _draft(client, "Second")
        assert client.post(
            f"/api/actions/proposals/{first}/approve", json={"reason": "fine"}
        ).status_code == 200

        page = client.get("/api/actions/proposals/changes", params={"limit": 2}).json()
        _ResourceChanges.model_validate(page)
        assert [event["data"]["kind"] for event in page["events"]] == ["drafted", "drafted"]
        assert [event["terminal"] for event in page["events"]] == [False, False]

        rest = client.get(
            "/api/actions/proposals/changes", params={"cursor": page["next_cursor"]}
        ).json()
        _ResourceChanges.model_validate(rest)
        assert len(rest["events"]) == 1
        approved = rest["events"][0]
        assert approved["terminal"] is True
        assert approved["data"] | {"occurred_at": None} == {
            "schema_version": "hla-action-proposal-event/v1",
            "repo_id": "homelab-analytics",
            "action_id": first,
            "sequence": 2,
            "kind": "approved",
            "occurred_at": None,
            "actor": None,
            "actor_auth_provider": None,
            "reason": "fine",
            "status": "approved",
            "effect_state": "accepted",
            "adapter": "platform",
            "source_kind": "agent",
            "origin": "mcp:propose_action",
            "title": "First",
            "proposal_path": f"/api/actions/proposals/{first}",
        }

        # Caught up: same cursor back, no events.
        idle = client.get(
            "/api/actions/proposals/changes", params={"cursor": rest["next_cursor"]}
        ).json()
        assert idle["events"] == []
        assert idle["next_cursor"] == rest["next_cursor"]

        # One proposal's events only, under its own reference.
        narrowed = client.get(
            "/api/actions/proposals/changes", params={"action_id": second}
        ).json()
        _ResourceChanges.model_validate(narrowed)
        assert narrowed["reference"] == f"action-proposals/{second}"
        assert [event["data"]["action_id"] for event in narrowed["events"]] == [second]

        # Event ids are stable across reads.
        again = client.get("/api/actions/proposals/changes").json()
        assert [event["event_id"] for event in again["events"]] == [
            event["event_id"] for event in page["events"] + rest["events"]
        ]


def test_changes_feed_rejects_foreign_cursor_and_bad_limit() -> None:
    with TemporaryDirectory() as tmp:
        client = _client(tmp)
        assert client.get(
            "/api/actions/proposals/changes", params={"cursor": "page-2"}
        ).status_code == 400
        assert client.get(
            "/api/actions/proposals/changes", params={"limit": 0}
        ).status_code == 422
        assert client.get(
            "/api/actions/proposals/changes", params={"limit": 501}
        ).status_code == 422
        # The fixed path is not shadowed by the {action_id} route.
        assert client.get("/api/actions/proposals/changes").status_code == 200


@pytest.mark.integration
@pytest.mark.slow
def test_postgres_migration_0020_backfills_existing_events() -> None:
    import psycopg

    from packages.storage.migration_runner import apply_pending_postgres_migrations
    from tests.postgres_test_support import running_postgres_container

    postgres_dir = ROOT / "migrations" / "postgres"
    with TemporaryDirectory() as tmp, running_postgres_container() as dsn:
        before = Path(tmp) / "before"
        before.mkdir()
        for migration in sorted(postgres_dir.glob("*.sql")):
            if migration.name < POSTGRES_MIGRATION.name:
                shutil.copy(migration, before / migration.name)
        with psycopg.connect(dsn) as conn:
            apply_pending_postgres_migrations(conn, before)
            conn.execute(
                "INSERT INTO action_proposals (action_id, policy_id, policy_name, verdict,"
                " notification_id, adapter, source_kind, status, created_at, metadata_json,"
                " updated_at) VALUES ('a1', 'p', 'P', 'notify', 'a1', 'platform', 'agent',"
                " 'dismissed', now(), '{}', now())"
            )
            conn.execute(
                "INSERT INTO action_proposal_events (event_id, action_id, sequence, kind,"
                " occurred_at) VALUES ('e2', 'a1', 2, 'dismissed', now() + interval '5 minutes'),"
                " ('e1', 'a1', 1, 'drafted', now())"
            )
            conn.commit()
            applied = apply_pending_postgres_migrations(conn, postgres_dir)
            assert POSTGRES_MIGRATION.stem in applied
            rows = conn.execute(
                "SELECT sequence, feed_position FROM action_proposal_events"
                " ORDER BY feed_position"
            ).fetchall()
            assert rows == [(1, 1), (2, 2)]
            assert conn.execute(
                "SELECT last_position FROM action_proposal_feed_counter"
            ).fetchall() == [(2,)]
