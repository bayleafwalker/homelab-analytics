"""Tests for the policy registry: migration, store CRUD, and rule schema validation."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from pydantic import ValidationError

from packages.platform.policy_schema import (
    RULE_SCHEMA_VERSION,
    ComparisonOperator,
    HaHelperStateComparisonRule,
    PublicationFreshnessComparisonRule,
    PublicationValueComparisonRule,
    VerdictMapping,
    parse_rule_document,
)
from packages.storage.control_plane import (
    PolicyDefinitionCreate,
    PolicyDefinitionUpdate,
)
from packages.storage.migration_runner import apply_pending_sqlite_migrations
from packages.storage.sqlite_policy_registry import SQLitePolicyRegistryMixin


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _PolicyStore(SQLitePolicyRegistryMixin):
    """Minimal concrete store backed by an in-memory SQLite connection."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        connection.row_factory = sqlite3.Row
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS policy_definitions (
                policy_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                description TEXT,
                policy_kind TEXT NOT NULL,
                rule_schema_version TEXT NOT NULL DEFAULT '1.0',
                rule_document TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                source_kind TEXT NOT NULL DEFAULT 'operator',
                creator TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

    def _connect(self):
        from contextlib import contextmanager

        @contextmanager
        def _ctx():
            yield self._connection

        return _ctx()


def _make_store() -> _PolicyStore:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return _PolicyStore(conn)


def _value_rule_doc() -> str:
    return json.dumps({
        "rule_kind": "publication_value_comparison",
        "publication_key": "monthly_cashflow",
        "field_name": "net",
        "operator": "lt",
        "threshold": 0,
        "unit": "currency",
    })


def _create(**kwargs) -> PolicyDefinitionCreate:
    now = datetime.now(UTC)
    return PolicyDefinitionCreate(
        policy_id=kwargs.get("policy_id", str(uuid.uuid4())),
        display_name=kwargs.get("display_name", "Test Policy"),
        policy_kind=kwargs.get("policy_kind", "publication_value_comparison"),
        rule_schema_version=kwargs.get("rule_schema_version", RULE_SCHEMA_VERSION),
        rule_document=kwargs.get("rule_document", _value_rule_doc()),
        enabled=kwargs.get("enabled", True),
        source_kind=kwargs.get("source_kind", "operator"),
        description=kwargs.get("description", None),
        creator=kwargs.get("creator", "test-user"),
        created_at=kwargs.get("created_at", now),
        updated_at=kwargs.get("updated_at", now),
    )


# ---------------------------------------------------------------------------
# Migration runner: 0007_policy_registry.sql is applied cleanly
# ---------------------------------------------------------------------------

def test_migration_0007_creates_policy_definitions_table() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    migrations_dir = Path(__file__).resolve().parents[1] / "migrations" / "sqlite"
    assert migrations_dir.exists()
    applied = apply_pending_sqlite_migrations(conn, migrations_dir)
    assert "0007_policy_registry" in applied
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    assert "policy_definitions" in tables


def test_migration_0007_is_idempotent() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    migrations_dir = Path(__file__).resolve().parents[1] / "migrations" / "sqlite"
    apply_pending_sqlite_migrations(conn, migrations_dir)
    applied_second = apply_pending_sqlite_migrations(conn, migrations_dir)
    assert "0007_policy_registry" not in applied_second


# ---------------------------------------------------------------------------
# SQLitePolicyRegistryMixin CRUD
# ---------------------------------------------------------------------------

def test_create_and_get_policy_definition() -> None:
    store = _make_store()
    create = _create(display_name="Net cashflow alert", creator="alice")
    record = store.create_policy_definition(create)

    assert record.policy_id == create.policy_id
    assert record.display_name == "Net cashflow alert"
    assert record.enabled is True
    assert record.source_kind == "operator"
    assert record.creator == "alice"

    fetched = store.get_policy_definition(create.policy_id)
    assert fetched == record


def test_get_missing_policy_raises_key_error() -> None:
    store = _make_store()
    with pytest.raises(KeyError):
        store.get_policy_definition("nonexistent-id")


def test_list_policy_definitions_all() -> None:
    store = _make_store()
    ids = [str(uuid.uuid4()) for _ in range(3)]
    for pid in ids:
        store.create_policy_definition(_create(policy_id=pid))
    records = store.list_policy_definitions()
    assert {r.policy_id for r in records} == set(ids)


def test_list_policy_definitions_source_kind_filter() -> None:
    store = _make_store()
    store.create_policy_definition(_create(source_kind="builtin"))
    store.create_policy_definition(_create(source_kind="operator"))
    builtins = store.list_policy_definitions(source_kind="builtin")
    operators = store.list_policy_definitions(source_kind="operator")
    assert len(builtins) == 1
    assert len(operators) == 1
    assert builtins[0].source_kind == "builtin"


def test_list_policy_definitions_enabled_only_filter() -> None:
    store = _make_store()
    store.create_policy_definition(_create(enabled=True))
    store.create_policy_definition(_create(enabled=False))
    enabled = store.list_policy_definitions(enabled_only=True)
    assert len(enabled) == 1
    assert enabled[0].enabled is True


def test_update_policy_enabled_state() -> None:
    store = _make_store()
    create = _create()
    store.create_policy_definition(create)
    updated = store.update_policy_definition(
        create.policy_id,
        PolicyDefinitionUpdate(enabled=False),
    )
    assert updated.enabled is False
    assert store.get_policy_definition(create.policy_id).enabled is False


def test_update_policy_display_name_and_rule_document() -> None:
    store = _make_store()
    create = _create()
    store.create_policy_definition(create)
    new_doc = json.dumps({
        "rule_kind": "publication_freshness_comparison",
        "publication_key": "monthly_cashflow",
        "operator": "gt",
        "threshold_hours": 48,
    })
    updated = store.update_policy_definition(
        create.policy_id,
        PolicyDefinitionUpdate(display_name="New Name", rule_document=new_doc),
    )
    assert updated.display_name == "New Name"
    assert updated.rule_document == new_doc


def test_update_missing_policy_raises_key_error() -> None:
    store = _make_store()
    with pytest.raises(KeyError):
        store.update_policy_definition("ghost", PolicyDefinitionUpdate(enabled=True))


def test_delete_policy_definition() -> None:
    store = _make_store()
    create = _create()
    store.create_policy_definition(create)
    store.delete_policy_definition(create.policy_id)
    with pytest.raises(KeyError):
        store.get_policy_definition(create.policy_id)


def test_delete_missing_policy_raises_key_error() -> None:
    store = _make_store()
    with pytest.raises(KeyError):
        store.delete_policy_definition("ghost")


# ---------------------------------------------------------------------------
# Rule schema: parse_rule_document
# ---------------------------------------------------------------------------

def test_parse_publication_value_comparison() -> None:
    doc = {
        "rule_kind": "publication_value_comparison",
        "publication_key": "monthly_cashflow",
        "field_name": "net",
        "operator": "lt",
        "threshold": -500,
        "unit": "currency",
    }
    rule = parse_rule_document(doc)
    assert isinstance(rule, PublicationValueComparisonRule)
    assert rule.operator == ComparisonOperator.LT
    assert rule.threshold == -500


def test_parse_publication_freshness_comparison() -> None:
    doc = {
        "rule_kind": "publication_freshness_comparison",
        "publication_key": "monthly_cashflow",
        "operator": "gt",
        "threshold_hours": 72.0,
    }
    rule = parse_rule_document(doc)
    assert isinstance(rule, PublicationFreshnessComparisonRule)
    assert rule.threshold_hours == 72.0


def test_parse_ha_helper_state_comparison() -> None:
    doc = {
        "rule_kind": "ha_helper_state_comparison",
        "entity_id": "input_boolean.kitchen_light_request",
        "operator": "eq",
        "expected_value": True,
    }
    rule = parse_rule_document(doc)
    assert isinstance(rule, HaHelperStateComparisonRule)
    assert rule.entity_id == "input_boolean.kitchen_light_request"


def test_parse_unknown_rule_kind_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Unknown rule_kind"):
        parse_rule_document({"rule_kind": "exec_python_code", "code": "os.system('rm -rf /')"})


def test_parse_missing_rule_kind_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Unknown rule_kind"):
        parse_rule_document({"publication_key": "monthly_cashflow"})


def test_extra_fields_rejected_in_rule_document() -> None:
    doc = {
        "rule_kind": "publication_value_comparison",
        "publication_key": "monthly_cashflow",
        "field_name": "net",
        "operator": "lt",
        "threshold": 0,
        "injected_field": "malicious_value",
    }
    with pytest.raises(ValidationError):
        parse_rule_document(doc)


def test_invalid_operator_rejected() -> None:
    doc = {
        "rule_kind": "publication_value_comparison",
        "publication_key": "monthly_cashflow",
        "field_name": "net",
        "operator": "exec",
        "threshold": 0,
    }
    with pytest.raises(ValidationError):
        parse_rule_document(doc)


def test_verdict_mapping_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        VerdictMapping.model_validate({"ok": "all_good", "unknown_field": "bad"})


# ---------------------------------------------------------------------------
# IngestionConfigRepository: policy methods available on concrete store
# ---------------------------------------------------------------------------

def test_ingestion_config_repository_has_policy_crud() -> None:
    from packages.storage.ingestion_config import IngestionConfigRepository
    with TemporaryDirectory() as tmp:
        repo = IngestionConfigRepository(Path(tmp) / "config.db")
        create = _create()
        record = repo.create_policy_definition(create)
        assert record.policy_id == create.policy_id
        records = repo.list_policy_definitions()
        assert any(r.policy_id == create.policy_id for r in records)
        repo.delete_policy_definition(create.policy_id)
        with pytest.raises(KeyError):
            repo.get_policy_definition(create.policy_id)
