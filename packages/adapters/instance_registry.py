"""In-memory registry of live adapter instances.

``AdapterRegistry`` tracks static ``AdapterPack`` declarations. Live
adapter *instances* — objects satisfying the ``IngestAdapter``,
``PublishAdapter``, or ``ActionAdapter`` protocols — hold references to
the workers doing real work. The runtime status API needs a way to look
them up by ``adapter_key``.

``AdapterInstanceRegistry`` is that lookup table. It is deliberately
minimal: registration by ``adapter_key``, iteration, and status snapshot
retrieval.
"""

from __future__ import annotations

import threading
from typing import Protocol, runtime_checkable

from packages.platform.adapter_runtime_status import AdapterRuntimeStatus


@runtime_checkable
class _StatusReporter(Protocol):
    """Any object exposing a typed status snapshot via ``get_status``."""

    def get_status(self) -> AdapterRuntimeStatus:
        ...  # pragma: no cover


class AdapterInstanceRegistry:
    """Thread-safe registry of live adapter instances keyed by adapter_key."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._instances: dict[str, _StatusReporter] = {}

    def register(self, adapter_key: str, instance: _StatusReporter) -> None:
        """Register a live adapter instance.

        Parameters
        ----------
        adapter_key:
            Stable identifier matching the wrapped adapter's manifest.
        instance:
            Any object whose ``get_status()`` returns ``AdapterRuntimeStatus``.
        """
        if not adapter_key:
            raise ValueError("adapter_key must be a non-empty string")
        with self._lock:
            self._instances[adapter_key] = instance

    def unregister(self, adapter_key: str) -> None:
        """Remove an adapter instance. Silent no-op when the key is absent."""
        with self._lock:
            self._instances.pop(adapter_key, None)

    def get(self, adapter_key: str) -> _StatusReporter | None:
        """Return the registered instance for ``adapter_key`` or ``None``."""
        with self._lock:
            return self._instances.get(adapter_key)

    def keys(self) -> list[str]:
        """Return registered adapter_keys sorted for determinism."""
        with self._lock:
            return sorted(self._instances.keys())

    def status(self, adapter_key: str) -> AdapterRuntimeStatus | None:
        """Return the current typed status for ``adapter_key``.

        Returns ``None`` when no instance is registered.
        """
        instance = self.get(adapter_key)
        if instance is None:
            return None
        return instance.get_status()

    def statuses(self) -> dict[str, AdapterRuntimeStatus]:
        """Return every registered instance's current status snapshot."""
        with self._lock:
            snapshot = dict(self._instances)
        return {key: instance.get_status() for key, instance in snapshot.items()}
