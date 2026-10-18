from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.application.use_cases.ops_metrics import (
    OpsMetricsCollector,
    build_ops_metrics_collector,
    collect_backup_status_metrics,
    collect_confidence_metrics,
    collect_ingestion_run_metrics,
    collect_source_freshness_metrics,
    collect_worker_heartbeat_metrics,
)
from packages.domains.finance.pipelines.account_transaction_service import (
    AccountTransactionService,
)
from packages.pipelines.reporting_service import (
    PUBLICATION_REFRESH_DURATION_METRIC,
    publish_promotion_reporting,
)
from packages.shared.metrics import MetricsRegistry, metrics_registry
from packages.storage.backup_bundle import BackupSources
from packages.storage.backup_schedule import BackupSchedulePolicy, run_scheduled_backup
from packages.storage.control_plane import (
    PublicationConfidenceSnapshotCreate,
    WorkerHeartbeatCreate,
)
from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.run_metadata import RunMetadataRepository
from tests.account_test_support import FIXTURES as ACCOUNT_FIXTURES

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


class _FreshnessConfigRepo:
    def list_source_assets(self, include_archived: bool = False):
        return [
            SimpleNamespace(source_asset_id="bank", name="Bank", dataset_contract_id="dc-bank"),
            SimpleNamespace(source_asset_id="power", name="Power", dataset_contract_id="dc-power"),
        ]

    def list_source_freshness_configs(self):
        return []

    def get_dataset_contract(self, dataset_contract_id: str):
        return SimpleNamespace(dataset_name=dataset_contract_id.removeprefix("dc-"))


class _RunListing:
    def list_runs(self, *, dataset_name: str | None = None):
        if dataset_name == "bank":
            # Naive timestamps are treated as UTC, never mixed with aware ones.
            return [
                SimpleNamespace(
                    run_id="run-1",
                    status="landed",
                    created_at=datetime(2026, 10, 18, 11, 0),
                )
            ]
        return []


def test_source_freshness_metrics_report_lag_and_one_hot_state() -> None:
    registry = MetricsRegistry()

    collect_source_freshness_metrics(registry, _FreshnessConfigRepo(), _RunListing(), now=NOW)

    text = registry.render_prometheus_text()
    labels = 'dataset="bank",source_asset_id="bank"'
    assert f"homelab_analytics_source_freshness_lag_seconds{{{labels}}} 3600" in text
    assert (
        f"homelab_analytics_source_last_landed_timestamp_seconds{{{labels}}} "
        f"{int(datetime(2026, 10, 18, 11, 0, tzinfo=UTC).timestamp())}"
    ) in text
    # A source that never landed exports no lag series, only its state.
    assert 'homelab_analytics_source_freshness_lag_seconds{dataset="power"' not in text
    assert (
        'homelab_analytics_source_freshness_state{dataset="power",'
        'source_asset_id="power",state="unconfigured"} 1'
    ) in text
    assert (
        'homelab_analytics_source_freshness_state{dataset="power",'
        'source_asset_id="power",state="current"} 0'
    ) in text


def test_confidence_metrics_use_latest_snapshot_per_publication() -> None:
    with TemporaryDirectory() as temp_dir:
        repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
        repository.record_publication_confidence_snapshot(
            (
                PublicationConfidenceSnapshotCreate(
                    snapshot_id="s1",
                    publication_key="monthly_cashflow",
                    assessed_at=NOW - timedelta(hours=2),
                    freshness_state="stale",
                    completeness_pct=40,
                    confidence_verdict="unreliable",
                ),
                PublicationConfidenceSnapshotCreate(
                    snapshot_id="s2",
                    publication_key="monthly_cashflow",
                    assessed_at=NOW - timedelta(hours=1),
                    freshness_state="current",
                    completeness_pct=100,
                    confidence_verdict="trustworthy",
                ),
                PublicationConfidenceSnapshotCreate(
                    snapshot_id="s3",
                    publication_key="utility_cost_summary",
                    assessed_at=NOW,
                    freshness_state="stale",
                    completeness_pct=60,
                    confidence_verdict="degraded",
                ),
            )
        )
        registry = MetricsRegistry()

        collect_confidence_metrics(registry, repository)

    text = registry.render_prometheus_text()
    assert 'homelab_analytics_publication_confidence_verdicts{verdict="trustworthy"} 1' in text
    assert 'homelab_analytics_publication_confidence_verdicts{verdict="degraded"} 1' in text
    assert 'homelab_analytics_publication_confidence_verdicts{verdict="unreliable"} 0' in text
    assert 'homelab_analytics_publication_confidence_verdicts{verdict="unavailable"} 0' in text
    assert (
        'homelab_analytics_publication_confidence_verdict{publication_key="monthly_cashflow",'
        'verdict="trustworthy"} 1'
    ) in text


def test_ingestion_run_and_heartbeat_metrics_come_from_durable_stores() -> None:
    with TemporaryDirectory() as temp_dir:
        service = AccountTransactionService(
            landing_root=Path(temp_dir) / "landing",
            metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
        )
        service.ingest_file(ACCOUNT_FIXTURES / "account_transactions_valid.csv")
        repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
        repository.record_worker_heartbeat(
            WorkerHeartbeatCreate(
                worker_id="w-old", status="stopped", observed_at=NOW - timedelta(hours=5)
            )
        )
        repository.record_worker_heartbeat(
            WorkerHeartbeatCreate(
                worker_id="w-new", status="idle", observed_at=NOW - timedelta(seconds=30)
            )
        )
        registry = MetricsRegistry()

        collect_ingestion_run_metrics(registry, service.metadata_repository)
        collect_worker_heartbeat_metrics(registry, repository, now=NOW)

    text = registry.render_prometheus_text()
    assert "# TYPE homelab_analytics_ingestion_runs_recorded_total counter" in text
    assert 'homelab_analytics_ingestion_runs_recorded_total{status="landed"} 1' in text
    assert 'homelab_analytics_ingestion_runs_recorded_total{status="failed"} 0' in text
    # Newest heartbeat, so a dead worker record from a previous pod does not
    # mask a healthy current worker.
    assert "homelab_analytics_worker_newest_heartbeat_age_seconds 30" in text


def test_backup_status_metrics_absent_then_present() -> None:
    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        registry = MetricsRegistry()
        collect_backup_status_metrics(registry, root / "backups")
        assert "homelab_analytics_backup_status_present 0" in registry.render_prometheus_text()

        sources = BackupSources(
            control_plane_backend="sqlite",
            reporting_backend="duckdb",
            blob_backend="filesystem",
            control_plane_database_path=root / "config.db",
            warehouse_database_path=root / "analytics" / "warehouse.duckdb",
            landing_root=root / "landing",
        )
        run_scheduled_backup(
            sources,
            BackupSchedulePolicy(root / "backups", interval_seconds=3600, retention_count=2),
            now=NOW,
        )
        collect_backup_status_metrics(registry, root / "backups")

    text = registry.render_prometheus_text()
    assert "homelab_analytics_backup_status_present 1" in text
    assert f"homelab_analytics_backup_last_success_timestamp_seconds {int(NOW.timestamp())}" in text
    assert "homelab_analytics_backup_consecutive_failures 0" in text
    assert "homelab_analytics_backup_successes_total 1" in text


def test_collector_is_rate_limited_and_isolates_failures() -> None:
    registry = MetricsRegistry()
    calls: list[str] = []
    clock = {"t": 0.0}

    def ok() -> None:
        calls.append("ok")

    def broken() -> None:
        raise RuntimeError("store down")

    collector = OpsMetricsCollector(
        registry=registry,
        collectors={"ok": ok, "broken": broken},
        min_interval_seconds=10,
        monotonic=lambda: clock["t"],
    )
    collector.collect()
    clock["t"] = 5
    collector.collect()
    clock["t"] = 11
    collector.collect()

    assert calls == ["ok", "ok"]
    text = registry.render_prometheus_text()
    assert 'homelab_analytics_metrics_collector_up{collector="ok"} 1' in text
    assert 'homelab_analytics_metrics_collector_up{collector="broken"} 0' in text
    assert 'homelab_analytics_metrics_collector_errors_total{collector="broken"} 2' in text


def test_publication_refresh_duration_is_observed_by_outcome() -> None:
    class _Reporting:
        def publish_publications(self, keys, run_id=None):
            return list(keys)

        def publish_auxiliary_relations(self, relations, run_id=None):
            return []

    class _Broken(_Reporting):
        def publish_publications(self, keys, run_id=None):
            raise RuntimeError("reporting store down")

    promotion = SimpleNamespace(
        publication_keys=["monthly_cashflow"], run_id="run-1", marts_refreshed=[]
    )
    before = metrics_registry.render_prometheus_text()
    assert publish_promotion_reporting(_Reporting(), promotion) == ["monthly_cashflow"]
    try:
        publish_promotion_reporting(_Broken(), promotion)
    except RuntimeError:
        pass
    after = metrics_registry.render_prometheus_text()

    def count(text: str, outcome: str) -> int:
        prefix = f'{PUBLICATION_REFRESH_DURATION_METRIC}_count{{outcome="{outcome}"}} '
        for line in text.splitlines():
            if line.startswith(prefix):
                return int(line.removeprefix(prefix))
        return 0

    assert count(after, "success") == count(before, "success") + 1
    assert count(after, "error") == count(before, "error") + 1


def _api_client(temp_dir: str) -> TestClient:
    service = AccountTransactionService(
        landing_root=Path(temp_dir) / "landing",
        metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
    )
    app = create_app(
        service,
        config_repository=IngestionConfigRepository(Path(temp_dir) / "config.db"),
    )
    return TestClient(app)


def test_api_metrics_expose_request_histogram_with_route_templates() -> None:
    with TemporaryDirectory() as temp_dir:
        client = _api_client(temp_dir)
        assert client.get("/health").status_code == 200
        client.get("/runs/does-not-exist")
        client.get("/no/such/route")

        text = client.get("/metrics").text

    assert (
        'homelab_analytics_http_requests_total{method="GET",route="/health",status="200"}'
        in text
    )
    assert 'route="/runs/{run_id}"' in text
    assert 'route="/runs/does-not-exist"' not in text
    assert 'route="unmatched"' in text
    assert (
        'homelab_analytics_http_request_duration_seconds_bucket{method="GET",'
        'route="/health",status_class="2xx",le="+Inf"}'
    ) in text
    assert "homelab_analytics_worker_newest_heartbeat_age_seconds -1" in text
    assert "homelab_analytics_backup_status_present 0" in text
    assert 'homelab_analytics_metrics_collector_up{collector="source_freshness"} 1' in text


def test_api_metrics_require_scrape_token_when_configured() -> None:
    from apps.api import app as app_module

    with TemporaryDirectory() as temp_dir:
        service = AccountTransactionService(
            landing_root=Path(temp_dir) / "landing",
            metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
        )
        application = app_module.FastAPI()
        repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
        app_module._register_base_routes(
            application,
            identity_mode="disabled",
            break_glass_controller=None,
            config_repository=repository,
            metrics_token="s3cret",
            ops_collector=build_ops_metrics_collector(
                MetricsRegistry(),
                config_repository=repository,
                metadata_repository=service.metadata_repository,
                backup_dir=None,
            ),
        )
        client = TestClient(application)

        assert client.get("/metrics").status_code == 401
        assert client.get("/metrics", headers={"Authorization": "Bearer s3cret"}).status_code == 401
        response = client.get("/metrics", headers={"Authorization": "Metrics s3cret"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
