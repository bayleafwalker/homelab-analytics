from __future__ import annotations

from wsgiref.simple_server import make_server

from apps.web.app import create_app
from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.reporting_service import ReportingService
from packages.pipelines.transformation_service import TransformationService
from packages.shared.settings import AppSettings
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.runtime import (
    build_blob_store,
    build_reporting_store,
    build_run_metadata_store,
)


def build_service(settings: AppSettings) -> AccountTransactionService:
    return AccountTransactionService(
        landing_root=settings.landing_root,
        metadata_repository=build_run_metadata_store(settings),
        blob_store=build_blob_store(settings),
    )


def build_transformation_service(settings: AppSettings) -> TransformationService:
    analytics_path = settings.resolved_analytics_database_path
    analytics_path.parent.mkdir(parents=True, exist_ok=True)
    return TransformationService(DuckDBStore.open(str(analytics_path)))


def build_reporting_service(
    settings: AppSettings,
    transformation_service: TransformationService,
) -> ReportingService:
    return ReportingService(
        transformation_service,
        publication_store=build_reporting_store(settings),
    )


def build_app(settings: AppSettings | None = None):
    resolved_settings = settings or AppSettings.from_env()
    transformation_service = build_transformation_service(resolved_settings)
    return create_app(
        build_service(resolved_settings),
        transformation_service=transformation_service,
        reporting_service=build_reporting_service(
            resolved_settings,
            transformation_service,
        ),
    )


def main() -> int:
    settings = AppSettings.from_env()
    app = build_app(settings)
    with make_server(settings.web_host, settings.web_port, app) as server:
        print(
            f"Serving homelab-analytics web on http://{settings.web_host}:{settings.web_port}"
        )
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
