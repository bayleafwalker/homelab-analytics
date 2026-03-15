from __future__ import annotations

from typing import cast

import uvicorn

from apps.api.app import create_app
from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.contract_price_service import ContractPriceService
from packages.pipelines.lazy_transformation_service import LazyTransformationService
from packages.pipelines.reporting_service import ReportingAccessMode, ReportingService
from packages.pipelines.subscription_service import SubscriptionService
from packages.pipelines.transformation_service import TransformationService
from packages.shared.auth import build_session_manager, maybe_bootstrap_local_admin
from packages.shared.extensions import ExtensionRegistry, load_extension_registry
from packages.shared.logging import configure_logging
from packages.shared.settings import AppSettings
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.runtime import (
    build_blob_store,
    build_config_store,
    build_reporting_store,
    build_run_metadata_store,
)


def build_service(settings: AppSettings) -> AccountTransactionService:
    return AccountTransactionService(
        landing_root=settings.landing_root,
        metadata_repository=build_run_metadata_store(settings),
        blob_store=build_blob_store(settings),
    )


def build_subscription_service(settings: AppSettings) -> SubscriptionService:
    return SubscriptionService(
        landing_root=settings.landing_root,
        metadata_repository=build_run_metadata_store(settings),
        blob_store=build_blob_store(settings),
    )


def build_contract_price_service(settings: AppSettings) -> ContractPriceService:
    return ContractPriceService(
        landing_root=settings.landing_root,
        metadata_repository=build_run_metadata_store(settings),
        blob_store=build_blob_store(settings),
    )


def build_transformation_service(settings: AppSettings) -> TransformationService:
    analytics_path = settings.resolved_analytics_database_path
    analytics_path.parent.mkdir(parents=True, exist_ok=True)
    return TransformationService(
        DuckDBStore.open(str(analytics_path)),
        control_plane_store=build_config_store(settings),
    )


def build_lazy_transformation_service(settings: AppSettings) -> TransformationService:
    return cast(
        TransformationService,
        LazyTransformationService(lambda: build_transformation_service(settings)),
    )


def build_reporting_service(
    settings: AppSettings,
    transformation_service: TransformationService,
    extension_registry: ExtensionRegistry | None = None,
    control_plane_store=None,
) -> ReportingService:
    return ReportingService(
        transformation_service,
        publication_store=build_reporting_store(settings),
        extension_registry=extension_registry,
        access_mode=(
            ReportingAccessMode.PUBLISHED
            if settings.reporting_backend.lower() == "postgres"
            else ReportingAccessMode.WAREHOUSE
        ),
        control_plane_store=control_plane_store,
    )


def build_extension_registry(settings: AppSettings) -> ExtensionRegistry:
    return load_extension_registry(
        extension_paths=settings.extension_paths,
        extension_modules=settings.extension_modules,
    )


def build_app(settings: AppSettings | None = None):
    resolved_settings = settings or AppSettings.from_env()
    config_store = build_config_store(resolved_settings)
    maybe_bootstrap_local_admin(config_store, resolved_settings)
    transformation_service = build_lazy_transformation_service(resolved_settings)
    extension_registry = build_extension_registry(resolved_settings)
    return create_app(
        build_service(resolved_settings),
        extension_registry,
        config_repository=config_store,
        transformation_service=transformation_service,
        reporting_service=build_reporting_service(
            resolved_settings,
            transformation_service,
            extension_registry,
            config_store,
        ),
        subscription_service=build_subscription_service(resolved_settings),
        contract_price_service=build_contract_price_service(resolved_settings),
        auth_store=config_store,
        auth_mode=resolved_settings.auth_mode,
        session_manager=build_session_manager(resolved_settings),
        auth_failure_window_seconds=resolved_settings.auth_failure_window_seconds,
        auth_failure_threshold=resolved_settings.auth_failure_threshold,
        auth_lockout_seconds=resolved_settings.auth_lockout_seconds,
        enable_unsafe_admin=resolved_settings.enable_unsafe_admin,
    )


def main() -> int:
    settings = AppSettings.from_env()
    configure_logging()
    uvicorn.run(
        build_app(settings),
        host=settings.api_host,
        port=settings.api_port,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
