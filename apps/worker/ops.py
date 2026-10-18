"""Worker-side operations: scheduled backups and the worker /metrics endpoint.

The scheduled backup runs *inside* the dispatch loop, at the idle yield point
between dispatches. Dispatch processing is synchronous on the loop thread and
every promotion closes its warehouse connection before returning, so at that
point this process holds no DuckDB handle and none of its own ingestion can be
in flight. ``create_backup`` then takes a read-only DuckDB connection, which
is retried with backoff while another process (an API write session, a long
promotion) holds
the write lock; the failure is recorded and retried later.
"""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from packages.application.use_cases.ops_metrics import collect_backup_status_metrics
from packages.shared.metrics import (
    METRICS_AUTH_SCHEME,
    MetricsRegistry,
    metrics_registry,
    scrape_token_matches,
)
from packages.shared.settings import AppSettings
from packages.storage.backup_bundle import BackupSources
from packages.storage.backup_schedule import (
    BackupSchedulePolicy,
    ScheduledBackupResult,
    backup_due,
    read_backup_status,
    run_scheduled_backup,
)

PREFIX = "homelab_analytics"


def record_loop_heartbeat(
    *, registry: MetricsRegistry = metrics_registry, now: datetime | None = None
) -> None:
    moment = now or datetime.now(UTC)
    registry.set(
        f"{PREFIX}_worker_loop_heartbeat_timestamp_seconds",
        moment.timestamp(),
        help_text="Unix time of the latest dispatch-loop iteration in this worker process.",
    )
    registry.inc(
        f"{PREFIX}_worker_loop_iterations_total",
        1,
        help_text="Dispatch-loop iterations completed by this worker process.",
    )


def record_dispatch_outcome(
    outcome: str, *, registry: MetricsRegistry = metrics_registry
) -> None:
    registry.inc(
        f"{PREFIX}_worker_dispatches_total",
        1,
        help_text="Schedule dispatches processed by this worker process, by outcome.",
        labels={"outcome": outcome},
    )


def backup_sources_from_settings(settings: AppSettings) -> BackupSources:
    """Map settings to store locations without carrying DSNs or credentials."""
    return BackupSources(
        control_plane_backend=settings.resolved_control_plane_backend,
        reporting_backend=settings.reporting_backend.lower(),
        blob_backend=settings.blob_backend.lower(),
        control_plane_database_path=settings.resolved_config_database_path,
        warehouse_database_path=settings.resolved_analytics_database_path,
        landing_root=settings.landing_root,
    )


def backup_policy_from_settings(settings: AppSettings) -> BackupSchedulePolicy:
    return BackupSchedulePolicy(
        destination_root=settings.resolved_backup_dir,
        interval_seconds=settings.backup_interval_seconds,
        retention_count=settings.backup_retention_count,
    )


class ScheduledBackupRunner:
    """Run a due backup at the loop's idle yield point."""

    def __init__(
        self,
        settings: AppSettings,
        *,
        logger: logging.Logger,
        registry: MetricsRegistry = metrics_registry,
        policy: BackupSchedulePolicy | None = None,
    ) -> None:
        self._settings = settings
        self._logger = logger
        self._registry = registry
        self.policy = policy or backup_policy_from_settings(settings)

    @property
    def enabled(self) -> bool:
        return self.policy.enabled

    def maybe_run(self, *, now: datetime | None = None) -> ScheduledBackupResult | None:
        if not self.enabled:
            return None
        moment = now or datetime.now(UTC)
        status = read_backup_status(self.policy.destination_root)
        if not backup_due(self.policy, status, now=moment):
            return None
        result = run_scheduled_backup(
            backup_sources_from_settings(self._settings),
            self.policy,
            now=moment,
        )
        collect_backup_status_metrics(self._registry, self.policy.destination_root)
        if result.succeeded:
            self._logger.info(
                "scheduled backup completed",
                extra={
                    "bundle": str(result.bundle_dir),
                    "pruned": [str(path) for path in result.pruned],
                    "duration_seconds": result.status.last_duration_seconds,
                },
            )
        else:
            self._logger.error(
                "scheduled backup failed",
                extra={
                    "error": result.error,
                    "consecutive_failures": result.status.consecutive_failures,
                },
            )
        return result


class WorkerMetricsServer:
    """Serve ``GET /metrics`` for the worker process on a background thread."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        token: str | None,
        registry: MetricsRegistry = metrics_registry,
        backup_dir: Path | None = None,
    ) -> None:
        registry_ref = registry
        token_ref = token
        backup_dir_ref = backup_dir

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - http.server API
                if self.path.split("?", 1)[0] != "/metrics":
                    self.send_error(404)
                    return
                if not scrape_token_matches(self.headers.get("Authorization"), token_ref):
                    self.send_response(401)
                    self.send_header("WWW-Authenticate", METRICS_AUTH_SCHEME)
                    self.end_headers()
                    return
                if backup_dir_ref is not None:
                    collect_backup_status_metrics(registry_ref, backup_dir_ref)
                body = registry_ref.render_prometheus_text().encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; version=0.0.4")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                return

        self._server = ThreadingHTTPServer((host, port), _Handler)
        self._server.daemon_threads = True
        self._thread = threading.Thread(
            target=self._server.serve_forever, name="worker-metrics", daemon=True
        )

    @property
    def port(self) -> int:
        return int(self._server.server_address[1])

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


def start_worker_metrics_server(
    settings: AppSettings, *, logger: logging.Logger
) -> WorkerMetricsServer | None:
    if settings.worker_metrics_port <= 0:
        return None
    server = WorkerMetricsServer(
        host=settings.worker_metrics_host,
        port=settings.worker_metrics_port,
        token=settings.metrics_token,
        backup_dir=settings.resolved_backup_dir,
    )
    server.start()
    logger.info("worker metrics endpoint listening", extra={"port": server.port})
    return server
