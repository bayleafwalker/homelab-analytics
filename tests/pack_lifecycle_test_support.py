"""Shared pack lifecycle store contract, run against SQLite and Postgres."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest

from packages.storage.pack_lifecycle import (
    PackInstallationRecord,
    PackLifecycleActor,
    PackLifecycleConflictError,
    PackLifecycleEventCreate,
    PackLifecycleStore,
    PackStateExpectation,
)

ACTOR = PackLifecycleActor(
    actor="admin-a",
    actor_role="admin",
    actor_auth_provider="local",
    actor_authenticated=True,
)
INSTALLED_AT = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)


def _installation() -> PackInstallationRecord:
    return PackInstallationRecord(
        pack_key="contract_pack",
        display_name="Contract Pack",
        pack_kind="domain",
        trust_level="community",
        installed_version="1.0.0",
        previous_version=None,
        pinned_version=None,
        enabled=True,
        extension_registry_source_id="src-1",
        extension_registry_revision_id="rev-1",
        entry_digest="digest-1",
        previous_entry_digest=None,
        available_versions='["1.0.0", "1.1.0"]',
        compatibility_snapshot='{"status": "compatible"}',
        installed_at=INSTALLED_AT,
        updated_at=INSTALLED_AT,
    )


def _event(event_id: str, action: str, **overrides: Any) -> PackLifecycleEventCreate:
    fields: dict[str, Any] = {
        "event_id": event_id,
        "pack_key": "contract_pack",
        "action": action,
        "outcome": "applied",
        "from_version": None,
        "to_version": "1.0.0",
        "reason": "contract test",
        "extension_registry_source_id": "src-1",
        "extension_registry_revision_id": "rev-1",
        "entry_digest": "digest-1",
        "compatibility_snapshot": "{}",
        "plan": "{}",
        "actor": ACTOR,
        "occurred_at": INSTALLED_AT,
    }
    fields.update(overrides)
    return PackLifecycleEventCreate(**fields)


def assert_pack_lifecycle_store_behaviour(store: Any) -> None:
    """Compare-and-set installation changes plus append-only lifecycle events."""
    assert isinstance(store, PackLifecycleStore)
    assert store.get_pack_installation("contract_pack") is None
    assert store.list_pack_installations() == []

    installation = _installation()
    install_event = store.apply_pack_lifecycle_change(
        installation,
        _event("evt-1", "install"),
        expected=PackStateExpectation(installed_version=None),
    )
    assert install_event.action == "install"
    assert install_event.actor == ACTOR
    assert install_event.occurred_at == INSTALLED_AT
    assert store.get_pack_installation("contract_pack") == installation

    # A second install planned against "not installed" is a conflict, and the
    # refused write leaves no event behind.
    with pytest.raises(PackLifecycleConflictError):
        store.apply_pack_lifecycle_change(
            installation,
            _event("evt-dup", "install"),
            expected=PackStateExpectation(installed_version=None),
        )

    upgraded_at = datetime(2026, 10, 2, 9, 0, tzinfo=UTC)
    upgraded = replace(
        installation,
        installed_version="1.1.0",
        previous_version="1.0.0",
        entry_digest="digest-2",
        previous_entry_digest="digest-1",
        extension_registry_revision_id="rev-2",
        updated_at=upgraded_at,
    )
    store.apply_pack_lifecycle_change(
        upgraded,
        _event(
            "evt-2",
            "upgrade",
            from_version="1.0.0",
            to_version="1.1.0",
            occurred_at=upgraded_at,
        ),
        expected=PackStateExpectation(installed_version="1.0.0", enabled=True),
    )
    assert store.get_pack_installation("contract_pack") == upgraded

    # Planning against the old version is refused without touching state.
    with pytest.raises(PackLifecycleConflictError):
        store.apply_pack_lifecycle_change(
            replace(upgraded, enabled=False),
            _event("evt-stale", "disable", occurred_at=upgraded_at),
            expected=PackStateExpectation(installed_version="1.0.0", enabled=True),
        )
    assert store.get_pack_installation("contract_pack") == upgraded

    refused = store.record_pack_lifecycle_event(
        _event(
            "evt-3",
            "upgrade",
            outcome="refused",
            from_version="1.1.0",
            to_version="2.0.0",
            plan='{"allowed": false}',
            occurred_at=datetime(2026, 10, 3, 9, 0, tzinfo=UTC),
        )
    )
    assert refused.outcome == "refused"
    assert store.get_pack_installation("contract_pack") == upgraded

    events = store.list_pack_lifecycle_events(pack_key="contract_pack")
    assert [event.event_id for event in events] == ["evt-3", "evt-2", "evt-1"]
    assert [event.event_id for event in store.list_pack_lifecycle_events(limit=1)] == [
        "evt-3"
    ]
    assert store.list_pack_lifecycle_events(pack_key="other") == []
    assert [record.pack_key for record in store.list_pack_installations()] == [
        "contract_pack"
    ]

    with pytest.raises(ValueError):
        store.record_pack_lifecycle_event(_event("evt-blank", "install", reason="  "))
    with pytest.raises(ValueError):
        store.record_pack_lifecycle_event(_event("evt-bad", "uninstall"))
