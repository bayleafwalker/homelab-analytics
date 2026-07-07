"""Pack lifecycle state machine.

Extends the low-level ``AdapterRegistry`` with an explicit lifecycle:

    NOT_INSTALLED --install--> INSTALLED
    INSTALLED     --activate--> ACTIVE
    INSTALLED     --uninstall--> NOT_INSTALLED
    ACTIVE        --deactivate--> INSTALLED
    ACTIVE        --upgrade--> ACTIVE (new version) [previous kept for rollback]
    INSTALLED     --upgrade--> INSTALLED (new version) [previous kept for rollback]
    ACTIVE        --rollback--> ACTIVE (previous)  [current parked for rollback]
    INSTALLED     --rollback--> INSTALLED (previous) [current parked for rollback]

``install`` requires the pack not to be installed already.
``uninstall`` refuses when the pack is ACTIVE — deactivate first.
``upgrade`` requires the target pack to share the same ``pack_key`` as
the currently installed one; the pre-upgrade contract check runs first
when a checker is supplied so an incompatible upgrade never touches
the active version.
``rollback`` requires a stored previous version.

Illegal transitions raise :class:`IllegalPackTransition` without
mutating registry state.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from packages.adapters.contracts import AdapterPack, CompatibilityCheck
from packages.adapters.pack_compatibility import PackCompatibilityChecker
from packages.adapters.registry import AdapterRegistry


class PackLifecycleState(str, Enum):
    NOT_INSTALLED = "not_installed"
    INSTALLED = "installed"
    ACTIVE = "active"


class IllegalPackTransition(RuntimeError):
    """A requested lifecycle transition is not allowed from the current state."""


@dataclass(frozen=True)
class UpgradeResult:
    """Outcome of an ``upgrade`` call.

    ``check`` is present when the caller supplied a checker; a rejected
    upgrade returns a ``CompatibilityCheck`` with ``is_compatible=False``
    and does not touch the registry. ``previous`` names the pack that
    remains parked for rollback on a successful upgrade.
    """

    upgraded: bool
    check: Optional[CompatibilityCheck]
    previous: Optional[AdapterPack]


class PackLifecycle:
    """State-machine wrapper around an :class:`AdapterRegistry`.

    Uses the registry as the source of truth for installed/active state
    and keeps a parallel ``_previous`` mapping of parked packs so that
    an upgrade can be rolled back exactly once. A subsequent successful
    upgrade or rollback replaces the parked version.
    """

    def __init__(self, registry: AdapterRegistry) -> None:
        self._registry = registry
        self._previous: dict[str, AdapterPack] = {}

    @property
    def registry(self) -> AdapterRegistry:
        return self._registry

    def state(self, pack_key: str) -> PackLifecycleState:
        pack = self._registry.get(pack_key)
        if pack is None:
            return PackLifecycleState.NOT_INSTALLED
        if self._registry.is_active(pack_key):
            return PackLifecycleState.ACTIVE
        return PackLifecycleState.INSTALLED

    def previous(self, pack_key: str) -> Optional[AdapterPack]:
        return self._previous.get(pack_key)

    def install(self, pack: AdapterPack) -> None:
        current = self.state(pack.pack_key)
        if current is not PackLifecycleState.NOT_INSTALLED:
            raise IllegalPackTransition(
                f"cannot install {pack.pack_key}: already {current.value}"
            )
        self._registry.register(pack)

    def uninstall(self, pack_key: str) -> None:
        current = self.state(pack_key)
        if current is PackLifecycleState.NOT_INSTALLED:
            raise IllegalPackTransition(
                f"cannot uninstall {pack_key}: not installed"
            )
        if current is PackLifecycleState.ACTIVE:
            raise IllegalPackTransition(
                f"cannot uninstall {pack_key} while active; deactivate first"
            )
        self._registry.unregister(pack_key)
        self._previous.pop(pack_key, None)

    def activate(self, pack_key: str) -> None:
        current = self.state(pack_key)
        if current is PackLifecycleState.NOT_INSTALLED:
            raise IllegalPackTransition(
                f"cannot activate {pack_key}: not installed"
            )
        if current is PackLifecycleState.ACTIVE:
            raise IllegalPackTransition(
                f"cannot activate {pack_key}: already active"
            )
        self._registry.activate(pack_key)

    def deactivate(self, pack_key: str) -> None:
        current = self.state(pack_key)
        if current is not PackLifecycleState.ACTIVE:
            raise IllegalPackTransition(
                f"cannot deactivate {pack_key}: not active (currently {current.value})"
            )
        self._registry.deactivate(pack_key)

    def upgrade(
        self,
        new_pack: AdapterPack,
        *,
        checker: Optional[PackCompatibilityChecker] = None,
    ) -> UpgradeResult:
        """Replace the installed pack with ``new_pack``.

        Requires that a pack with the same ``pack_key`` is already
        installed (INSTALLED or ACTIVE). When ``checker`` is supplied,
        the compatibility check runs before any state mutation; an
        incompatible upgrade returns an ``UpgradeResult`` with
        ``upgraded=False`` and leaves the registry untouched.
        """
        current_state = self.state(new_pack.pack_key)
        if current_state is PackLifecycleState.NOT_INSTALLED:
            raise IllegalPackTransition(
                f"cannot upgrade {new_pack.pack_key}: not installed"
            )

        current_pack = self._registry.get(new_pack.pack_key)
        assert current_pack is not None  # Guarded by state check above.

        check: Optional[CompatibilityCheck] = None
        if checker is not None:
            check = checker.check(new_pack)
            if not check.is_compatible:
                return UpgradeResult(upgraded=False, check=check, previous=None)

        was_active = current_state is PackLifecycleState.ACTIVE
        self._registry.unregister(new_pack.pack_key)
        self._registry.register(new_pack)
        if was_active:
            self._registry.activate(new_pack.pack_key)
        self._previous[new_pack.pack_key] = current_pack

        return UpgradeResult(upgraded=True, check=check, previous=current_pack)

    def rollback(self, pack_key: str) -> AdapterPack:
        """Restore the previous version of ``pack_key``.

        The pack that is currently installed becomes the parked
        rollback target for the restored version, so an operator can
        rollback again to undo the rollback if needed.
        """
        current_state = self.state(pack_key)
        if current_state is PackLifecycleState.NOT_INSTALLED:
            raise IllegalPackTransition(
                f"cannot rollback {pack_key}: not installed"
            )
        previous_pack = self._previous.get(pack_key)
        if previous_pack is None:
            raise IllegalPackTransition(
                f"cannot rollback {pack_key}: no previous version parked"
            )

        current_pack = self._registry.get(pack_key)
        assert current_pack is not None

        was_active = current_state is PackLifecycleState.ACTIVE
        self._registry.unregister(pack_key)
        self._registry.register(previous_pack)
        if was_active:
            self._registry.activate(pack_key)
        self._previous[pack_key] = current_pack

        return previous_pack


__all__ = [
    "IllegalPackTransition",
    "PackLifecycle",
    "PackLifecycleState",
    "UpgradeResult",
]
