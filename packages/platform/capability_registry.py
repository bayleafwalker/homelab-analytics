from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from types import ModuleType

from packages.platform.capability_types import CapabilityPack
from packages.shared.extensions import load_extension_modules


class CapabilityPackRegistry:
    def __init__(self) -> None:
        self._packs_by_name: dict[str, CapabilityPack] = {}

    def register(self, pack: CapabilityPack) -> None:
        pack.validate()
        existing = self._packs_by_name.get(pack.name)
        if existing is not None and existing != pack:
            raise ValueError(f"Capability pack already registered: {pack.name}")
        self._packs_by_name[pack.name] = pack

    def list_packs(self) -> tuple[CapabilityPack, ...]:
        return tuple(
            self._packs_by_name[name]
            for name in sorted(self._packs_by_name)
        )


def load_capability_packs(
    *,
    builtin_packs: Sequence[CapabilityPack] = (),
    extension_paths: tuple[Path, ...] = (),
    extension_modules: tuple[str, ...] = (),
) -> tuple[CapabilityPack, ...]:
    registry = CapabilityPackRegistry()
    for pack in builtin_packs:
        registry.register(pack)

    loaded_modules = load_extension_modules(
        extension_paths=extension_paths,
        extension_modules=extension_modules,
    )
    for module_name, module in zip(extension_modules, loaded_modules, strict=True):
        _register_module_capability_packs(module_name, module, registry)

    return registry.list_packs()


def _register_module_capability_packs(
    module_name: str,
    module: ModuleType,
    registry: CapabilityPackRegistry,
) -> None:
    register_capability_packs = getattr(module, "register_capability_packs", None)
    if register_capability_packs is None:
        return
    if not callable(register_capability_packs):
        raise ValueError(
            f"Extension module {module_name!r} must define callable register_capability_packs(registry)"
        )
    register_capability_packs(registry)
