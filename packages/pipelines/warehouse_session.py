"""Short-lived DuckDB warehouse handles for long-running, mostly-reading processes.

DuckDB admits one read-write *process* per database file. The API used to open
the warehouse read-write on first use and keep it for its lifetime, which locked
out the worker's promotions and its scheduled backups. This module replaces that
with handles that are:

- **read-only by default.** ``get_*``/``count_*``/``list_*`` calls and store
  reads (``fetchall*``/``query_*``) run on a read-only connection, which
  coexists with read-only openers in other processes (the backup guard);
- **read-write only for writes**, for the duration of the call(s) that need it;
- **closed when idle**: at the end of the last in-flight request (the API
  installs a request hook) or after ``idle_timeout_seconds`` without use;
- **retried on lock conflicts**: opening while another process holds the write
  lock is retried with backoff, then :class:`WarehouseBusyError` is raised
  (the API maps it to 503).

The read-only service skips schema bootstrap (``_ensure_schema`` issues DDL);
the manager bootstraps the schema once per process with a brief read-write
open when it can, and the worker keeps the schema current as well.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, TypeVar

import duckdb

from packages.pipelines.transformation_service import TransformationService
from packages.shared.metrics import MetricsRegistry, metrics_registry
from packages.storage.duckdb_store import DuckDBStore, WarehouseBusyError

__all__ = [
    "READ_METHOD_PREFIXES",
    "STORE_READ_METHODS",
    "WarehouseBusyError",
    "WarehouseSessionManager",
    "WarehouseSessionTransformationService",
    "is_read_method",
]

READ_METHOD_PREFIXES: tuple[str, ...] = ("get_", "count_", "list_")
STORE_READ_METHODS = frozenset({"fetchall", "fetchall_dicts", "query_current", "query_as_of"})
MODE_READ_ONLY = "read_only"
MODE_READ_WRITE = "read_write"
_HANDLE_GAUGE = "homelab_analytics_api_warehouse_handle_open"
_HANDLE_HELP = "1 while this process holds a DuckDB warehouse handle in the given mode."

T = TypeVar("T")
_logger = logging.getLogger("homelab_analytics.warehouse_session")


# Read-named facet methods whose implementation still issues DDL
# (``ensure_*_storage`` / CREATE IF NOT EXISTS) before reading, so they need a
# read-write handle. tests/test_api_warehouse_sessions.py scans the facets and
# fails when a new one appears that is not listed here.
READ_NAMED_WRITE_METHODS = frozenset(
    {
        "get_ha_entities",
        "get_ha_entity_history",
        "get_scenario",
        "get_scenario_assumptions",
        "get_scenario_view",
        "list_scenario_compare_sets",
        "list_scenarios",
    }
)


def is_read_method(name: str) -> bool:
    return name.startswith(READ_METHOD_PREFIXES) and name not in READ_NAMED_WRITE_METHODS


def _is_read_only_violation(exc: BaseException) -> bool:
    return isinstance(exc, duckdb.Error) and "read-only mode" in str(exc)


class _ReadOnlyTransformationService(TransformationService):
    """TransformationService over a read-only connection: no schema DDL."""

    def _ensure_schema(self) -> None:
        return None


ServiceFactory = Callable[[DuckDBStore, bool], TransformationService]


class WarehouseSessionManager:
    def __init__(
        self,
        database_path: Path,
        build_service: ServiceFactory,
        *,
        idle_timeout_seconds: float = 5.0,
        lock_retry_attempts: int = 4,
        lock_retry_backoff_seconds: float = 0.1,
        registry: MetricsRegistry = metrics_registry,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._path = database_path
        self._build_service = build_service
        self.idle_timeout_seconds = idle_timeout_seconds
        self._lock_retry_attempts = lock_retry_attempts
        self._lock_retry_backoff_seconds = lock_retry_backoff_seconds
        self._registry = registry
        self._monotonic = monotonic
        self._cond = threading.Condition()
        self._service: TransformationService | None = None
        self._mode: str | None = None
        self._inflight = 0
        self._active_requests = 0
        self._last_used = monotonic()
        self._schema_ready = False
        self._close_when_drained = False
        self._holders = threading.local()
        self._reaper: threading.Thread | None = None
        self._stopped = threading.Event()
        self._publish_state()

    # -- state ---------------------------------------------------------------

    @property
    def mode(self) -> str | None:
        """``read_only``, ``read_write`` or ``None`` when no handle is held."""
        return self._mode

    def _publish_state(self) -> None:
        for mode in (MODE_READ_ONLY, MODE_READ_WRITE):
            self._registry.set(
                _HANDLE_GAUGE,
                1.0 if self._mode == mode else 0.0,
                help_text=_HANDLE_HELP,
                labels={"mode": mode},
            )

    # -- open / close ----------------------------------------------------------

    def _open_store(self, *, read_only: bool) -> DuckDBStore:
        try:
            return DuckDBStore.open(
                str(self._path),
                read_only=read_only,
                lock_retry_attempts=self._lock_retry_attempts,
                lock_retry_backoff_seconds=self._lock_retry_backoff_seconds,
            )
        except WarehouseBusyError:
            self._registry.inc(
                "homelab_analytics_api_warehouse_busy_total",
                1,
                help_text="Warehouse opens that gave up because another process held the lock.",
            )
            raise

    def _bootstrap_schema(self) -> None:
        """Ensure the warehouse schema once per process via a brief read-write open."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            store = self._open_store(read_only=False)
        except WarehouseBusyError:
            if self._path.exists():
                # The writer (worker) keeps the schema current; read as-is.
                return
            raise
        try:
            self._build_service(store, False)
        finally:
            store.close()
        self._schema_ready = True

    def _open(self, mode: str) -> None:
        if not self._schema_ready:
            self._bootstrap_schema()
        read_only = mode == MODE_READ_ONLY
        store = self._open_store(read_only=read_only)
        try:
            self._service = self._build_service(store, read_only)
        except BaseException:
            store.close()
            raise
        self._mode = mode
        self._registry.inc(
            "homelab_analytics_api_warehouse_opens_total",
            1,
            help_text="Warehouse handles opened by this process, by mode.",
            labels={"mode": mode},
        )
        self._publish_state()

    def _close_locked(self) -> None:
        if self._service is not None:
            try:
                self._service.store.close()
            finally:
                self._service = None
                self._mode = None
                self._publish_state()

    def close(self) -> None:
        with self._cond:
            while self._inflight:
                self._cond.wait()
            self._close_locked()

    def close_if_idle(self) -> bool:
        with self._cond:
            if self._service is None or self._inflight:
                return False
            if self._monotonic() - self._last_used < self.idle_timeout_seconds:
                return False
            self._close_locked()
            return True

    # -- leases ----------------------------------------------------------------

    @contextmanager
    def lease(self, *, write: bool) -> Iterator[TransformationService]:
        wanted = MODE_READ_WRITE if write else MODE_READ_ONLY
        held = getattr(self._holders, "depth", 0)
        with self._cond:
            while True:
                if self._service is not None and (
                    self._mode == MODE_READ_WRITE or wanted == MODE_READ_ONLY
                ):
                    break
                if self._inflight == 0:
                    self._close_locked()
                    self._open(wanted)
                    break
                if held:
                    raise RuntimeError(
                        "Nested warehouse write inside a read-only lease on the same thread."
                    )
                self._cond.wait()
            self._inflight += 1
            service = self._service
            assert service is not None
        self._holders.depth = held + 1
        try:
            yield service
        finally:
            self._holders.depth = held
            with self._cond:
                self._inflight -= 1
                self._last_used = self._monotonic()
                if self._inflight == 0 and self._active_requests == 0 and (
                    self._close_when_drained or self.idle_timeout_seconds <= 0
                ):
                    self._close_when_drained = False
                    self._close_locked()
                self._cond.notify_all()

    def call(self, label: str, fn: Callable[[TransformationService], T], *, write: bool) -> T:
        if not write:
            try:
                with self.lease(write=False) as service:
                    return fn(service)
            except duckdb.Error as exc:
                if not _is_read_only_violation(exc):
                    raise
                _logger.warning(
                    "warehouse read lease attempted a write; retrying read-write",
                    extra={"method": label},
                )
                self._registry.inc(
                    "homelab_analytics_api_warehouse_write_upgrades_total",
                    1,
                    help_text="Calls classified as reads that needed a read-write handle.",
                    labels={"method": label},
                )
        with self.lease(write=True) as service:
            return fn(service)

    # -- request scope ---------------------------------------------------------

    def begin_request(self) -> None:
        with self._cond:
            self._active_requests += 1

    def end_request(self) -> None:
        """Release the handle once the last in-flight request finishes."""
        with self._cond:
            self._active_requests = max(0, self._active_requests - 1)
            if self._active_requests:
                return
            if self._inflight:
                # A background lease is still running: close when it drains.
                self._close_when_drained = True
                return
            self._close_locked()

    # -- idle reaper -----------------------------------------------------------

    def start_reaper(self) -> None:
        """Close handles held outside requests (background threads) when idle."""
        if self._reaper is not None or self.idle_timeout_seconds <= 0:
            return
        interval = max(0.05, self.idle_timeout_seconds / 2)

        def _run() -> None:
            while not self._stopped.wait(interval):
                self.close_if_idle()

        self._reaper = threading.Thread(target=_run, name="warehouse-reaper", daemon=True)
        self._reaper.start()

    def stop(self) -> None:
        self._stopped.set()
        self.close()


class _StoreProxy:
    """Stand-in for ``service.store``: each call takes its own lease."""

    def __init__(self, manager: WarehouseSessionManager) -> None:
        self._manager = manager

    def __getattr__(self, name: str) -> Any:
        if name == "close":
            return self._manager.close

        def _call(*args: Any, **kwargs: Any) -> Any:
            return self._manager.call(
                f"store.{name}",
                lambda service: getattr(service.store, name)(*args, **kwargs),
                write=name not in STORE_READ_METHODS,
            )

        return _call


class WarehouseSessionTransformationService:
    """TransformationService facade whose every call runs on a short-lived handle."""

    def __init__(self, manager: WarehouseSessionManager) -> None:
        self._manager = manager

    @property
    def warehouse_sessions(self) -> WarehouseSessionManager:
        return self._manager

    @property
    def store(self) -> _StoreProxy:
        return _StoreProxy(self._manager)

    @property
    def _store(self) -> _StoreProxy:
        return _StoreProxy(self._manager)

    def close(self) -> None:
        self._manager.close()

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__"):
            raise AttributeError(name)
        attribute = getattr(TransformationService, name, None)
        if callable(attribute):

            def _call(*args: Any, **kwargs: Any) -> Any:
                return self._manager.call(
                    name,
                    lambda service: getattr(service, name)(*args, **kwargs),
                    write=not is_read_method(name),
                )

            return _call
        with self._manager.lease(write=False) as service:
            return getattr(service, name)


def build_read_only_aware_service_factory(
    **service_kwargs: Any,
) -> ServiceFactory:
    """Factory building the full service read-write and a DDL-free one read-only."""

    def _build(store: DuckDBStore, read_only: bool) -> TransformationService:
        cls = _ReadOnlyTransformationService if read_only else TransformationService
        return cls(store, **service_kwargs)

    return _build
