"""Scrape-time operational metrics derived from durable stores.

The API and worker are separate processes, so in-process counters only see
their own work. Everything an SLO or alert depends on across processes is
derived here from the control plane, run metadata, and the backup status file
at scrape time: source freshness lag, latest confidence verdicts, recorded
ingestion outcomes, worker heartbeats, and backup recency.

Collectors are rate-limited (``min_interval_seconds``) so a fast scrape
interval does not turn into a query storm, and a failing collector is
reported via ``homelab_analytics_metrics_collector_up`` instead of failing
the scrape.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packages.application.use_cases.source_freshness_overview import (
    build_source_freshness_views,
)
from packages.platform.publication_confidence import ConfidenceVerdict
from packages.platform.source_freshness import SourceFreshnessState
from packages.shared.metrics import MetricsRegistry
from packages.storage.backup_drill import read_restore_drill_status
from packages.storage.backup_schedule import read_backup_status
from packages.storage.run_metadata import IngestionRunStatus

__all__ = [
    "OpsMetricsCollector",
    "collect_backup_status_metrics",
    "collect_confidence_metrics",
    "collect_ingestion_run_metrics",
    "collect_source_freshness_metrics",
    "collect_worker_heartbeat_metrics",
]

PREFIX = "homelab_analytics"
_logger = logging.getLogger("homelab_analytics.ops_metrics")


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _iso_to_epoch(value: str | None) -> float:
    if not value:
        return 0.0
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def collect_source_freshness_metrics(
    registry: MetricsRegistry,
    config_repository: Any,
    metadata_repository: Any,
    *,
    now: datetime,
) -> None:
    now = _as_utc(now)
    views = build_source_freshness_views(
        config_repository, metadata_repository, as_of=now.date()
    )
    landed: list[tuple[Mapping[str, object], float]] = []
    lag: list[tuple[Mapping[str, object], float]] = []
    overdue: list[tuple[Mapping[str, object], float]] = []
    states: list[tuple[Mapping[str, object], float]] = []
    for view in views:
        labels = {"source_asset_id": view.source_asset_id, "dataset": view.dataset_name}
        if view.landed_at is not None:
            landed_at = _as_utc(view.landed_at)
            landed.append((labels, landed_at.timestamp()))
            lag.append((labels, max(0.0, (now - landed_at).total_seconds())))
        overdue_seconds = 0.0
        if view.next_expected_at is not None:
            overdue_seconds = max(
                0.0, (now - _as_utc(view.next_expected_at)).total_seconds()
            )
        overdue.append((labels, overdue_seconds))
        for state in SourceFreshnessState:
            states.append(
                (
                    {**labels, "state": str(state)},
                    1.0 if view.freshness_state == state else 0.0,
                )
            )
    registry.replace_series(
        f"{PREFIX}_source_last_landed_timestamp_seconds",
        landed,
        help_text="Unix time of the latest landed run per source asset.",
    )
    registry.replace_series(
        f"{PREFIX}_source_freshness_lag_seconds",
        lag,
        help_text="Seconds since the latest landed run per source asset.",
    )
    registry.replace_series(
        f"{PREFIX}_source_overdue_seconds",
        overdue,
        help_text=(
            "Seconds a source asset is past its next expected ingest "
            "(0 when on time or no freshness config)."
        ),
    )
    registry.replace_series(
        f"{PREFIX}_source_freshness_state",
        states,
        help_text="1 for the current freshness state of each source asset, else 0.",
    )


def collect_confidence_metrics(registry: MetricsRegistry, config_repository: Any) -> None:
    latest: dict[str, Any] = {}
    for record in config_repository.list_publication_confidence_snapshots():
        current = latest.get(record.publication_key)
        if current is None or _as_utc(record.assessed_at) > _as_utc(current.assessed_at):
            latest[record.publication_key] = record
    counts = {str(verdict): 0 for verdict in ConfidenceVerdict}
    per_publication: list[tuple[Mapping[str, object], float]] = []
    assessed: list[tuple[Mapping[str, object], float]] = []
    for key, record in sorted(latest.items()):
        verdict = str(record.confidence_verdict)
        counts[verdict] = counts.get(verdict, 0) + 1
        for candidate in counts:
            per_publication.append(
                (
                    {"publication_key": key, "verdict": candidate},
                    1.0 if candidate == verdict else 0.0,
                )
            )
        assessed.append(
            ({"publication_key": key}, _as_utc(record.assessed_at).timestamp())
        )
    registry.replace_series(
        f"{PREFIX}_publication_confidence_verdicts",
        [({"verdict": verdict}, float(count)) for verdict, count in sorted(counts.items())],
        help_text="Publications whose latest confidence snapshot has each verdict.",
    )
    registry.replace_series(
        f"{PREFIX}_publication_confidence_verdict",
        per_publication,
        help_text="1 for the latest confidence verdict of each publication, else 0.",
    )
    registry.replace_series(
        f"{PREFIX}_publication_confidence_assessed_timestamp_seconds",
        assessed,
        help_text="Unix time of the latest confidence assessment per publication.",
    )


def collect_ingestion_run_metrics(registry: MetricsRegistry, metadata_repository: Any) -> None:
    registry.replace_series(
        f"{PREFIX}_ingestion_runs_recorded_total",
        [
            ({"status": str(status)}, float(metadata_repository.count_runs(status=status)))
            for status in IngestionRunStatus
        ],
        help_text=(
            "Ingestion runs recorded in run metadata by status, across API and "
            "worker processes."
        ),
        metric_type="counter",
    )


def collect_worker_heartbeat_metrics(
    registry: MetricsRegistry, config_repository: Any, *, now: datetime
) -> None:
    now = _as_utc(now)
    heartbeats = config_repository.list_worker_heartbeats()
    newest = max((_as_utc(beat.observed_at) for beat in heartbeats), default=None)
    registry.set(
        f"{PREFIX}_worker_last_heartbeat_timestamp_seconds",
        newest.timestamp() if newest is not None else 0.0,
        help_text="Unix time of the most recent heartbeat from any worker (0 if none).",
    )
    registry.set(
        f"{PREFIX}_worker_newest_heartbeat_age_seconds",
        max(0.0, (now - newest).total_seconds()) if newest is not None else -1.0,
        help_text=(
            "Seconds since the most recent heartbeat from any worker "
            "(-1 if no worker ever reported)."
        ),
    )


def collect_backup_status_metrics(registry: MetricsRegistry, backup_dir: Path) -> None:
    drill = read_restore_drill_status(backup_dir)
    if drill is not None:
        registry.set(
            f"{PREFIX}_backup_restore_drill_last_success_timestamp_seconds",
            _iso_to_epoch(drill.get("last_success_at")),
            help_text="Unix time of the last passing restore drill (0 if never).",
        )
        registry.set(
            f"{PREFIX}_backup_restore_drill_last_passed",
            1.0 if drill.get("passed") else 0.0,
            help_text="1 when the most recent restore drill passed.",
        )
    status = read_backup_status(backup_dir)
    registry.set(
        f"{PREFIX}_backup_status_present",
        1.0 if status is not None else 0.0,
        help_text="1 when a scheduled-backup status file exists in the backup directory.",
    )
    if status is None:
        return
    registry.set(
        f"{PREFIX}_backup_last_success_timestamp_seconds",
        _iso_to_epoch(status.last_success_at),
        help_text="Unix time of the last verified scheduled backup (0 if never).",
    )
    registry.set(
        f"{PREFIX}_backup_last_attempt_timestamp_seconds",
        _iso_to_epoch(status.last_attempt_at),
        help_text="Unix time of the last scheduled backup attempt.",
    )
    registry.set(
        f"{PREFIX}_backup_last_failure_timestamp_seconds",
        _iso_to_epoch(status.last_failure_at),
        help_text="Unix time of the last failed scheduled backup (0 if never).",
    )
    registry.set(
        f"{PREFIX}_backup_consecutive_failures",
        float(status.consecutive_failures),
        help_text="Scheduled backup failures since the last success.",
    )
    registry.set(
        f"{PREFIX}_backup_last_duration_seconds",
        float(status.last_duration_seconds or 0.0),
        help_text="Duration of the last scheduled backup attempt.",
    )
    registry.set(
        f"{PREFIX}_backup_last_size_bytes",
        float(status.last_size_bytes or 0),
        help_text="Size of the last verified backup bundle.",
    )
    registry.set(
        f"{PREFIX}_backup_bundles_retained",
        float(status.bundles_retained),
        help_text="Complete backup bundles currently retained on disk.",
    )
    registry.set(
        f"{PREFIX}_backup_successes_total",
        float(status.successes_total),
        help_text="Scheduled backups that completed and verified.",
        metric_type="counter",
    )
    registry.set(
        f"{PREFIX}_backup_failures_total",
        float(status.failures_total),
        help_text="Scheduled backups that failed.",
        metric_type="counter",
    )


@dataclass
class OpsMetricsCollector:
    """Run named collectors at most once per ``min_interval_seconds``."""

    registry: MetricsRegistry
    collectors: Mapping[str, Callable[[], None]]
    min_interval_seconds: float = 15.0
    monotonic: Callable[[], float] = time.monotonic
    _last_run: float | None = field(default=None, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def collect(self, *, force: bool = False) -> None:
        with self._lock:
            now = self.monotonic()
            if (
                not force
                and self._last_run is not None
                and now - self._last_run < self.min_interval_seconds
            ):
                return
            self._last_run = now
            for name, collector in self.collectors.items():
                try:
                    collector()
                except Exception:  # noqa: BLE001 - one bad store must not fail the scrape
                    _logger.warning("metrics collector failed", extra={"collector": name}, exc_info=True)
                    self.registry.set(
                        f"{PREFIX}_metrics_collector_up",
                        0.0,
                        help_text="1 when the named scrape-time collector last succeeded.",
                        labels={"collector": name},
                    )
                    self.registry.inc(
                        f"{PREFIX}_metrics_collector_errors_total",
                        1.0,
                        help_text="Scrape-time collector failures.",
                        labels={"collector": name},
                    )
                else:
                    self.registry.set(
                        f"{PREFIX}_metrics_collector_up",
                        1.0,
                        help_text="1 when the named scrape-time collector last succeeded.",
                        labels={"collector": name},
                    )


def build_ops_metrics_collector(
    registry: MetricsRegistry,
    *,
    config_repository: Any,
    metadata_repository: Any | None,
    backup_dir: Path | None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    min_interval_seconds: float = 15.0,
) -> OpsMetricsCollector:
    collectors: dict[str, Callable[[], None]] = {
        "confidence": lambda: collect_confidence_metrics(registry, config_repository),
        "worker_heartbeat": lambda: collect_worker_heartbeat_metrics(
            registry, config_repository, now=clock()
        ),
    }
    if metadata_repository is not None:
        collectors["source_freshness"] = lambda: collect_source_freshness_metrics(
            registry, config_repository, metadata_repository, now=clock()
        )
        collectors["ingestion_runs"] = lambda: collect_ingestion_run_metrics(
            registry, metadata_repository
        )
    if backup_dir is not None:
        collectors["backup_status"] = lambda: collect_backup_status_metrics(
            registry, backup_dir
        )
    return OpsMetricsCollector(
        registry=registry,
        collectors=collectors,
        min_interval_seconds=min_interval_seconds,
    )
