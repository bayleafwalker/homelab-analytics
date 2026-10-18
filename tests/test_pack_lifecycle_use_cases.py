"""Pack lifecycle use cases: discovery, dry-run plans, safety refusals, history."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from packages.application.use_cases.pack_lifecycle import (
    PackChangeRefusedError,
    PackLifecycleValidationError,
    apply_pack_change,
    build_pack_catalog,
    build_pack_lifecycle_context,
    plan_pack_change,
)
from packages.shared.pack_catalog import discover_cached_pack_entries
from packages.storage.external_registry_catalog import ExtensionRegistrySourceCreate
from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.pack_lifecycle import PackLifecycleActor
from tests.pack_lifecycle_test_support import (
    pack_entry,
    platform_pack,
    write_registry_revision,
)

ACTOR = PackLifecycleActor(
    actor="admin", actor_role="admin", actor_auth_provider="local", actor_authenticated=True
)
PLATFORM_VERSION = "0.5.0"


@pytest.fixture
def store(tmp_path: Path) -> IngestionConfigRepository:
    return IngestionConfigRepository(tmp_path / "config.db")


def _context(store: IngestionConfigRepository, *platform: Any):
    return build_pack_lifecycle_context(
        store,
        platform_packs=platform or (platform_pack("core", "core_summary"),),
        platform_version=PLATFORM_VERSION,
    )


def _apply(store, action: str, pack_key: str = "energy", version: str | None = None, **kw):
    return apply_pack_change(
        _context(store),
        pack_key=pack_key,
        action=action,
        version=version,
        reason=kw.pop("reason", f"{action} for test"),
        actor=ACTOR,
        **kw,
    )


def _seed_energy(store, root: Path) -> Path:
    return write_registry_revision(
        store,
        root,
        source_id="acme",
        revision_id="rev-1",
        packs=[
            pack_entry("energy", "1.0.0", publications={"energy_tariffs": "1.0.0"}),
            pack_entry("energy", "1.1.0", publications={"energy_tariffs": "1.1.0"}),
            pack_entry(
                "energy",
                "2.0.0",
                publications={"energy_tariffs": "2.0.0", "energy_forecast": "1.0.0"},
            ),
        ],
    )


# --- discovery ---------------------------------------------------------------


def test_discovery_reads_only_validated_cached_revisions(store, tmp_path: Path) -> None:
    _seed_energy(store, tmp_path)
    write_registry_revision(
        store,
        tmp_path,
        source_id="acme",
        revision_id="rev-failed",
        create_source=False,
        sync_status="failed",
        packs=[pack_entry("ghost", "1.0.0")],
    )
    store.create_extension_registry_source(
        ExtensionRegistrySourceCreate(
            extension_registry_source_id="off",
            name="disabled",
            source_kind="path",
            location=str(tmp_path / "off"),
            enabled=False,
        )
    )
    reads: list[Path] = []

    def reader(path: Path) -> str:
        reads.append(path)
        return path.read_text(encoding="utf-8")

    result = discover_cached_pack_entries(store, read_text=reader)

    assert [(e.pack_key, e.version) for e in result.entries] == [
        ("energy", "1.0.0"),
        ("energy", "1.1.0"),
        ("energy", "2.0.0"),
    ]
    assert result.errors == ()
    assert result.sources_scanned == 1
    # Only the validated revision's local manifest was read; nothing else.
    assert reads == [tmp_path / "acme" / "rev-1" / "homelab-analytics.registry.json"]
    assert all(e.entry_digest and e.manifest_digest for e in result.entries)


def test_discovery_reports_tampered_missing_and_malformed_manifests(
    store, tmp_path: Path
) -> None:
    manifest = _seed_energy(store, tmp_path)
    payload = json.loads(manifest.read_text())
    payload["extension_modules"] = ["swapped_module"]
    manifest.write_text(json.dumps(payload))
    write_registry_revision(
        store,
        tmp_path,
        source_id="bad",
        revision_id="rev-bad",
        packs=[{"pack_key": "broken"}, pack_entry("fine", "1.0.0")],
    )
    gone = write_registry_revision(
        store, tmp_path, source_id="gone", revision_id="rev-gone", packs=[]
    )
    gone.unlink()

    result = discover_cached_pack_entries(store)

    assert [(e.pack_key, e.version) for e in result.entries] == [("fine", "1.0.0")]
    joined = " | ".join(result.errors)
    assert "changed since it was synced" in joined
    assert "requires 'version'" in joined
    assert "cached manifest is missing" in joined


# --- install and dry-run ----------------------------------------------------


def test_dry_run_plan_shows_publications_and_contracts_without_writing(
    store, tmp_path: Path
) -> None:
    _seed_energy(store, tmp_path)
    result = _apply(store, "install", version="1.0.0", dry_run=True, reason="")

    assert result.dry_run and result.event is None
    plan = result.plan.to_dict()
    assert plan["allowed"] is True
    assert plan["to_version"] == "1.0.0"
    assert plan["publication_changes"] == [
        {
            "publication_key": "energy_tariffs",
            "change": "added",
            "from_schema_version": None,
            "to_schema_version": "1.0.0",
            "breaking": False,
            "dependents": [],
        }
    ]
    assert plan["contracts_affected"] == ["energy_tariffs@1.0.0"]
    assert store.get_pack_installation("energy") is None
    assert store.list_pack_lifecycle_events() == []


def test_install_defaults_to_latest_and_records_history(store, tmp_path: Path) -> None:
    _seed_energy(store, tmp_path)
    result = _apply(store, "install")

    installation = store.get_pack_installation("energy")
    assert installation is not None
    assert installation.installed_version == "2.0.0"
    assert installation.enabled is True
    assert installation.extension_registry_revision_id == "rev-1"
    assert json.loads(installation.available_versions) == ["1.0.0", "1.1.0", "2.0.0"]
    assert json.loads(installation.compatibility_snapshot)["status"] == "compatible"
    assert result.event is not None and result.event.outcome == "applied"
    [event] = store.list_pack_lifecycle_events(pack_key="energy")
    assert event.action == "install" and event.actor == ACTOR
    assert event.reason == "install for test"
    assert json.loads(event.plan)["contracts_affected"] == [
        "energy_forecast@1.0.0",
        "energy_tariffs@2.0.0",
    ]


def test_reason_is_required_and_actions_are_validated(store, tmp_path: Path) -> None:
    _seed_energy(store, tmp_path)
    with pytest.raises(PackLifecycleValidationError):
        _apply(store, "install", reason="   ")
    with pytest.raises(PackLifecycleValidationError):
        _apply(store, "install", reason="x" * 501)
    with pytest.raises(PackLifecycleValidationError):
        plan_pack_change(_context(store), pack_key="energy", action="uninstall")
    assert store.list_pack_lifecycle_events() == []


@pytest.mark.parametrize(
    ("entry", "code"),
    [
        (pack_entry("energy", "1.0.0", requires_platform_version=">=9.0"), "compatibility"),
        (pack_entry("energy", "1.0.0", dependencies=["missing_pack>=1.0"]), "compatibility"),
        (pack_entry("energy", "1.0.0", trust_level="verified"), "untrusted_verified_claim"),
        (
            pack_entry("energy", "1.0.0", publications={"core_summary": "1.0.0"}),
            "publication_conflict",
        ),
    ],
)
def test_install_refuses_incompatible_entries_and_records_refusal(
    store, tmp_path: Path, entry: dict[str, Any], code: str
) -> None:
    write_registry_revision(store, tmp_path, source_id="acme", revision_id="rev-1", packs=[entry])

    with pytest.raises(PackChangeRefusedError) as refused:
        _apply(store, "install", version="1.0.0")

    assert code in {d.code for d in refused.value.plan.diagnostics}
    assert refused.value.event.outcome == "refused"
    assert store.get_pack_installation("energy") is None
    [event] = store.list_pack_lifecycle_events()
    assert event.outcome == "refused"
    assert json.loads(event.compatibility_snapshot)["status"] == "incompatible"


def test_install_refuses_versions_not_in_the_local_cache(store, tmp_path: Path) -> None:
    _seed_energy(store, tmp_path)
    with pytest.raises(PackChangeRefusedError) as refused:
        _apply(store, "install", version="9.9.9")
    assert [d.code for d in refused.value.plan.diagnostics] == ["not_in_registry_cache"]
    with pytest.raises(PackChangeRefusedError):
        _apply(store, "install", pack_key="unknown")


def test_unknown_publication_relation_is_a_warning_not_a_refusal(
    store, tmp_path: Path
) -> None:
    write_registry_revision(
        store,
        tmp_path,
        source_id="acme",
        revision_id="rev-1",
        packs=[pack_entry("energy", "1.0.0", requires_publications=["not_published_yet"])],
    )
    result = _apply(store, "install", version="1.0.0")
    assert result.plan.compatibility_status == "warning"
    assert store.get_pack_installation("energy") is not None


# --- upgrade, rollback and publication safety -------------------------------


def test_upgrade_parks_previous_version_and_rollback_is_reversible(
    store, tmp_path: Path
) -> None:
    _seed_energy(store, tmp_path)
    _apply(store, "install", version="1.0.0")

    upgrade = _apply(store, "upgrade", version="1.1.0")
    assert [c.change for c in upgrade.plan.publication_changes] == ["schema_changed"]
    assert upgrade.plan.publication_changes[0].breaking is False
    installation = store.get_pack_installation("energy")
    assert (installation.installed_version, installation.previous_version) == ("1.1.0", "1.0.0")

    _apply(store, "rollback")
    installation = store.get_pack_installation("energy")
    assert (installation.installed_version, installation.previous_version) == ("1.0.0", "1.1.0")

    _apply(store, "rollback")
    assert store.get_pack_installation("energy").installed_version == "1.1.0"
    actions = [e.action for e in store.list_pack_lifecycle_events(pack_key="energy")]
    assert actions == ["rollback", "rollback", "upgrade", "install"]


def test_upgrade_refuses_same_older_and_uninstalled_targets(store, tmp_path: Path) -> None:
    _seed_energy(store, tmp_path)
    with pytest.raises(PackChangeRefusedError):
        _apply(store, "upgrade", version="1.1.0")
    _apply(store, "install", version="1.1.0")
    for version in ("1.1.0", "1.0.0"):
        with pytest.raises(PackChangeRefusedError) as refused:
            _apply(store, "upgrade", version=version)
        assert refused.value.plan.diagnostics[0].code == "illegal_transition"
    with pytest.raises(PackChangeRefusedError) as refused:
        _apply(store, "rollback")
    assert refused.value.plan.diagnostics[0].code == "no_rollback_target"


def _seed_consumer(store, tmp_path: Path) -> None:
    write_registry_revision(
        store,
        tmp_path,
        source_id="consumer",
        revision_id="rev-c",
        packs=[
            pack_entry(
                "budgets",
                "1.0.0",
                publications={"energy_budget": "1.0.0"},
                requires_publications=["energy_tariffs"],
                dependencies=["energy>=1.0,<2.0"],
            )
        ],
    )


def test_upgrade_refuses_to_break_a_publication_another_pack_requires(
    store, tmp_path: Path
) -> None:
    write_registry_revision(
        store,
        tmp_path,
        source_id="acme",
        revision_id="rev-1",
        packs=[
            pack_entry("energy", "1.0.0", publications={"energy_tariffs": "1.0.0"}),
            pack_entry("energy", "2.0.0", publications={"energy_tariffs_v2": "1.0.0"}),
            pack_entry("energy", "3.0.0", publications={"energy_tariffs": "2.0.0"}),
        ],
    )
    _seed_consumer(store, tmp_path)
    _apply(store, "install", version="1.0.0")
    _apply(store, "install", pack_key="budgets", version="1.0.0")

    with pytest.raises(PackChangeRefusedError) as removed:
        _apply(store, "upgrade", version="2.0.0")
    codes = {d.code for d in removed.value.plan.diagnostics}
    assert {"would_break_publication", "would_break_dependency"} <= codes
    removal = next(
        c for c in removed.value.plan.publication_changes if c.publication_key == "energy_tariffs"
    )
    assert removal.change == "removed" and removal.dependents == ("budgets",)

    with pytest.raises(PackChangeRefusedError) as major:
        _apply(store, "upgrade", version="3.0.0")
    assert "would_break_publication" in {d.code for d in major.value.plan.diagnostics}
    assert store.get_pack_installation("energy").installed_version == "1.0.0"


def test_disable_refuses_while_dependents_are_enabled_then_enable_rechecks(
    store, tmp_path: Path
) -> None:
    _seed_energy(store, tmp_path)
    _seed_consumer(store, tmp_path)
    _apply(store, "install", version="1.0.0")
    _apply(store, "install", pack_key="budgets", version="1.0.0")

    with pytest.raises(PackChangeRefusedError) as refused:
        _apply(store, "disable")
    assert "would_break_publication" in {d.code for d in refused.value.plan.diagnostics}

    _apply(store, "disable", pack_key="budgets")
    assert store.get_pack_installation("budgets").enabled is False
    disabled = _apply(store, "disable")
    assert [c.change for c in disabled.plan.publication_changes] == ["removed"]
    assert store.get_pack_installation("energy").enabled is False

    with pytest.raises(PackChangeRefusedError):
        _apply(store, "disable")
    enabled = _apply(store, "enable")
    assert [c.change for c in enabled.plan.publication_changes] == ["added"]
    assert store.get_pack_installation("energy").enabled is True


def test_rollback_and_enable_refuse_when_the_cached_entry_changed(
    store, tmp_path: Path
) -> None:
    manifest = _seed_energy(store, tmp_path)
    _apply(store, "install", version="1.0.0")
    _apply(store, "upgrade", version="1.1.0")
    payload = json.loads(manifest.read_text())
    payload["packs"][0]["description"] = "silently changed after install"
    manifest.write_text(json.dumps(payload))

    with pytest.raises(PackChangeRefusedError) as refused:
        _apply(store, "rollback")
    assert "cached_entry_changed" in {d.code for d in refused.value.plan.diagnostics}
    assert store.get_pack_installation("energy").installed_version == "1.1.0"


def test_pin_blocks_version_changes_until_unpinned(store, tmp_path: Path) -> None:
    _seed_energy(store, tmp_path)
    _apply(store, "install", version="1.0.0")
    _apply(store, "pin")
    assert store.get_pack_installation("energy").pinned_version == "1.0.0"

    with pytest.raises(PackChangeRefusedError) as refused:
        _apply(store, "upgrade", version="1.1.0")
    assert "pinned" in {d.code for d in refused.value.plan.diagnostics}

    _apply(store, "unpin")
    _apply(store, "upgrade", version="1.1.0")
    assert store.get_pack_installation("energy").installed_version == "1.1.0"


def test_catalog_marks_relations_and_compatibility_badges(store, tmp_path: Path) -> None:
    _seed_energy(store, tmp_path)
    write_registry_revision(
        store,
        tmp_path,
        source_id="future",
        revision_id="rev-f",
        packs=[pack_entry("solar", "1.0.0", requires_platform_version=">=9.0")],
    )
    _apply(store, "install", version="1.0.0")
    _apply(store, "upgrade", version="1.1.0")

    catalog = build_pack_catalog(_context(store))

    assert catalog["platform_version"] == PLATFORM_VERSION
    assert catalog["registry"]["sources_scanned"] == 2
    packs = {pack["pack_key"]: pack for pack in catalog["packs"]}
    energy = packs["energy"]
    assert energy["state"] == "enabled"
    assert energy["upgrade_available"] is True
    assert {row["version"]: row["relation"] for row in energy["versions"]} == {
        "2.0.0": "upgrade",
        "1.1.0": "installed",
        "1.0.0": "rollback",
    }
    solar = packs["solar"]
    assert solar["state"] == "not_installed"
    assert solar["versions"][0]["compatibility_status"] == "incompatible"
    assert catalog["platform_packs"] == [
        {"name": "core", "version": "1.0.0", "publication_count": 1}
    ]


def test_loaded_extension_pack_does_not_conflict_with_its_own_catalog_entry(
    store, tmp_path: Path
) -> None:
    write_registry_revision(
        store,
        tmp_path,
        source_id="acme",
        revision_id="rev-1",
        packs=[pack_entry("energy", "1.0.0", publications={"energy_tariffs": "1.0.0"})],
    )
    context = build_pack_lifecycle_context(
        store,
        platform_packs=(platform_pack("core"), platform_pack("energy", "energy_tariffs")),
        platform_version=PLATFORM_VERSION,
    )
    plan = plan_pack_change(
        context, pack_key="energy", action="install", now=datetime(2026, 10, 1, tzinfo=UTC)
    )
    assert plan.allowed
