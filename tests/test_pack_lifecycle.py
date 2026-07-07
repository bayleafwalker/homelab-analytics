"""Tests for the pack lifecycle state machine and pre-upgrade contract check."""

from __future__ import annotations

import pytest

from packages.adapters.contracts import AdapterPack, TrustLevel
from packages.adapters.lifecycle import (
    IllegalPackTransition,
    PackLifecycle,
    PackLifecycleState,
)
from packages.adapters.pack_compatibility import PackCompatibilityChecker
from packages.adapters.registry import AdapterRegistry


def _pack(pack_key: str, *, version: str = "1.0.0", requires: str = "") -> AdapterPack:
    return AdapterPack(
        pack_key=pack_key,
        display_name=pack_key,
        version=version,
        trust_level=TrustLevel.LOCAL,
        requires_platform_version=requires,
    )


@pytest.fixture
def lifecycle() -> PackLifecycle:
    return PackLifecycle(AdapterRegistry())


def test_initial_state_is_not_installed(lifecycle):
    assert lifecycle.state("unknown") is PackLifecycleState.NOT_INSTALLED


def test_install_transitions_to_installed(lifecycle):
    pack = _pack("example")
    lifecycle.install(pack)
    assert lifecycle.state("example") is PackLifecycleState.INSTALLED


def test_install_twice_is_illegal(lifecycle):
    lifecycle.install(_pack("example"))
    with pytest.raises(IllegalPackTransition):
        lifecycle.install(_pack("example"))


def test_activate_transitions_installed_to_active(lifecycle):
    lifecycle.install(_pack("example"))
    lifecycle.activate("example")
    assert lifecycle.state("example") is PackLifecycleState.ACTIVE


def test_activate_uninstalled_pack_is_illegal(lifecycle):
    with pytest.raises(IllegalPackTransition):
        lifecycle.activate("ghost")


def test_activate_active_pack_is_illegal(lifecycle):
    lifecycle.install(_pack("example"))
    lifecycle.activate("example")
    with pytest.raises(IllegalPackTransition):
        lifecycle.activate("example")


def test_deactivate_active_pack_returns_to_installed(lifecycle):
    lifecycle.install(_pack("example"))
    lifecycle.activate("example")
    lifecycle.deactivate("example")
    assert lifecycle.state("example") is PackLifecycleState.INSTALLED


def test_deactivate_installed_pack_is_illegal(lifecycle):
    lifecycle.install(_pack("example"))
    with pytest.raises(IllegalPackTransition):
        lifecycle.deactivate("example")


def test_uninstall_active_pack_is_illegal(lifecycle):
    lifecycle.install(_pack("example"))
    lifecycle.activate("example")
    with pytest.raises(IllegalPackTransition):
        lifecycle.uninstall("example")


def test_uninstall_installed_pack_returns_to_not_installed(lifecycle):
    lifecycle.install(_pack("example"))
    lifecycle.uninstall("example")
    assert lifecycle.state("example") is PackLifecycleState.NOT_INSTALLED


def test_upgrade_replaces_installed_version_and_parks_previous(lifecycle):
    old = _pack("example", version="1.0.0")
    new = _pack("example", version="1.1.0")
    lifecycle.install(old)

    result = lifecycle.upgrade(new)

    assert result.upgraded
    assert result.previous == old
    assert lifecycle.registry.get("example") == new
    assert lifecycle.previous("example") == old


def test_upgrade_preserves_active_state(lifecycle):
    old = _pack("example", version="1.0.0")
    new = _pack("example", version="1.1.0")
    lifecycle.install(old)
    lifecycle.activate("example")

    lifecycle.upgrade(new)

    assert lifecycle.state("example") is PackLifecycleState.ACTIVE


def test_upgrade_uninstalled_pack_is_illegal(lifecycle):
    with pytest.raises(IllegalPackTransition):
        lifecycle.upgrade(_pack("ghost"))


def test_rollback_restores_previous_and_parks_current(lifecycle):
    old = _pack("example", version="1.0.0")
    new = _pack("example", version="1.1.0")
    lifecycle.install(old)
    lifecycle.upgrade(new)

    restored = lifecycle.rollback("example")

    assert restored == old
    assert lifecycle.registry.get("example") == old
    assert lifecycle.previous("example") == new


def test_rollback_without_previous_is_illegal(lifecycle):
    lifecycle.install(_pack("example"))
    with pytest.raises(IllegalPackTransition):
        lifecycle.rollback("example")


def test_rollback_uninstalled_pack_is_illegal(lifecycle):
    with pytest.raises(IllegalPackTransition):
        lifecycle.rollback("ghost")


def test_double_rollback_returns_to_upgraded_version(lifecycle):
    old = _pack("example", version="1.0.0")
    new = _pack("example", version="1.1.0")
    lifecycle.install(old)
    lifecycle.upgrade(new)
    lifecycle.rollback("example")  # back to old
    restored = lifecycle.rollback("example")  # forward to new

    assert restored == new


def test_pre_upgrade_check_blocks_incompatible_upgrade(lifecycle):
    installed = _pack("example", version="1.0.0", requires="")
    incoming = _pack("example", version="2.0.0", requires=">=99.0.0")
    lifecycle.install(installed)
    checker = PackCompatibilityChecker(
        platform_version="0.2.0",
        installed_packs={},
    )

    result = lifecycle.upgrade(incoming, checker=checker)

    assert not result.upgraded
    assert result.check is not None
    assert not result.check.is_compatible
    # Registry state must not have changed.
    assert lifecycle.registry.get("example") == installed
    assert lifecycle.previous("example") is None


def test_pre_upgrade_check_allows_compatible_upgrade(lifecycle):
    installed = _pack("example", version="1.0.0")
    incoming = _pack("example", version="1.1.0", requires=">=0.1.0")
    lifecycle.install(installed)
    checker = PackCompatibilityChecker(
        platform_version="0.2.0",
        installed_packs={},
    )

    result = lifecycle.upgrade(incoming, checker=checker)

    assert result.upgraded
    assert result.check is not None
    assert result.check.is_compatible
    assert lifecycle.registry.get("example") == incoming
    assert lifecycle.previous("example") == installed
