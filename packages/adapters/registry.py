"""In-memory registry for adapter packs.

Provides thread-safe registration, activation, and lifecycle management of
adapter packs. Each pack is identified by its pack_key and can be activated
or deactivated independently.
"""

from __future__ import annotations

import threading
from typing import Optional

from packages.adapters.contracts import AdapterPack


class AdapterRegistry:
    """
    In-memory registry of adapter packs. Tracks registered packs and their
    activation state. Thread-safe via a simple lock.

    Each pack is identified by its pack_key. A pack must be registered before
    it can be activated. Only one pack with a given pack_key can exist.
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._lock = threading.Lock()
        self._packs: dict[str, AdapterPack] = {}
        self._active: dict[str, bool] = {}

    def register(self, pack: AdapterPack) -> None:
        """
        Add a pack to the registry.

        Parameters
        ----------
        pack
            The adapter pack to register.

        Raises
        ------
        ValueError
            If a pack with the same pack_key is already registered.
        """
        with self._lock:
            if pack.pack_key in self._packs:
                raise ValueError(
                    f"Pack with key '{pack.pack_key}' is already registered"
                )
            self._packs[pack.pack_key] = pack
            self._active[pack.pack_key] = False

    def activate(self, pack_key: str) -> None:
        """
        Mark a registered pack as active.

        Parameters
        ----------
        pack_key
            The key of the pack to activate.

        Raises
        ------
        KeyError
            If the pack is not registered.
        """
        with self._lock:
            if pack_key not in self._packs:
                raise KeyError(f"Pack '{pack_key}' is not registered")
            self._active[pack_key] = True

    def deactivate(self, pack_key: str) -> None:
        """
        Mark a registered pack as inactive.

        Parameters
        ----------
        pack_key
            The key of the pack to deactivate.

        Raises
        ------
        KeyError
            If the pack is not registered.
        """
        with self._lock:
            if pack_key not in self._packs:
                raise KeyError(f"Pack '{pack_key}' is not registered")
            self._active[pack_key] = False

    def list_packs(self, *, active_only: bool = False) -> list[AdapterPack]:
        """
        Return all registered packs, or only active ones.

        Parameters
        ----------
        active_only
            If True, return only active packs. Otherwise return all packs.

        Returns
        -------
        list[AdapterPack]
            Registered packs, ordered by pack_key for determinism.
        """
        with self._lock:
            if active_only:
                packs = [
                    self._packs[key]
                    for key in sorted(self._packs.keys())
                    if self._active[key]
                ]
            else:
                packs = [self._packs[key] for key in sorted(self._packs.keys())]
            return packs

    def is_active(self, pack_key: str) -> bool:
        """
        Check if a pack is registered and active.

        Parameters
        ----------
        pack_key
            The key of the pack to check.

        Returns
        -------
        bool
            True if the pack is registered and active, False otherwise.
        """
        with self._lock:
            return self._active.get(pack_key, False)

    def get(self, pack_key: str) -> Optional[AdapterPack]:
        """
        Get a registered pack by key.

        Parameters
        ----------
        pack_key
            The key of the pack to retrieve.

        Returns
        -------
        AdapterPack | None
            The pack if registered, None otherwise.
        """
        with self._lock:
            return self._packs.get(pack_key)

    def unregister(self, pack_key: str) -> None:
        """
        Remove a pack from the registry.

        Parameters
        ----------
        pack_key
            The key of the pack to remove.

        Raises
        ------
        KeyError
            If the pack is not registered.
        """
        with self._lock:
            if pack_key not in self._packs:
                raise KeyError(f"Pack '{pack_key}' is not registered")
            del self._packs[pack_key]
            del self._active[pack_key]
