from __future__ import annotations

import logging
from typing import cast

import uvicorn

from apps.api.app import create_app
from packages.domains.finance.manifest import FINANCE_PACK
from packages.domains.homelab.manifest import HOMELAB_PACK
from packages.domains.overview.manifest import OVERVIEW_PACK
from packages.domains.utilities.manifest import UTILITIES_PACK
from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.lazy_transformation_service import LazyTransformationService
from packages.pipelines.reporting_service import ReportingAccessMode, ReportingService
from packages.pipelines.transformation_service import TransformationService
from packages.platform.auth.configuration import validate_auth_configuration
from packages.platform.auth.oidc_provider import build_oidc_provider
from packages.platform.auth.session_manager import build_session_manager
from packages.platform.runtime.builder import build_container
from packages.platform.runtime.builder import (
    build_function_registry as _platform_build_function_registry,
)
from packages.shared.logging import configure_logging
from packages.shared.settings import AppSettings
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.runtime import (
    build_blob_store,
    build_config_store,
    build_reporting_store,
    build_run_metadata_store,
)


def build_function_registry(settings: AppSettings, *, config_repository=None):
    return _platform_build_function_registry(settings, config_repository=config_repository)


def build_service(settings: AppSettings) -> AccountTransactionService:
    return AccountTransactionService(
        landing_root=settings.landing_root,
        metadata_repository=build_run_metadata_store(settings),
        blob_store=build_blob_store(settings),
    )


def build_transformation_service(
    settings: AppSettings,
    *,
    container=None,
) -> TransformationService:
    analytics_path = settings.resolved_analytics_database_path
    analytics_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_container = container or build_container(settings)
    return TransformationService(
        DuckDBStore.open(str(analytics_path)),
        control_plane_store=resolved_container.control_plane_store,
        publication_refresh_registry=resolved_container.publication_refresh_registry,
        domain_registry=resolved_container.transformation_domain_registry,
    )


def build_lazy_transformation_service(
    settings: AppSettings,
    *,
    container=None,
) -> TransformationService:
    resolved_container = container or build_container(settings)
    return cast(
        TransformationService,
        LazyTransformationService(
            lambda: build_transformation_service(settings, container=resolved_container)
        ),
    )


def build_reporting_service(
    settings: AppSettings,
    transformation_service: TransformationService,
    extension_registry=None,
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
        control_plane_store=control_plane_store or build_config_store(settings),
    )


def build_app(settings: AppSettings | None = None):
    resolved_settings = settings or AppSettings.from_env()
    validate_auth_configuration(resolved_settings)

    container = build_container(resolved_settings, capability_packs=[FINANCE_PACK, UTILITIES_PACK, OVERVIEW_PACK, HOMELAB_PACK])

    transformation_service = build_lazy_transformation_service(
        resolved_settings, container=container
    )
    reporting_service = build_reporting_service(
        resolved_settings,
        transformation_service,
        container.extension_registry,
        container.control_plane_store,
    )

    ha_bridge = None
    if resolved_settings.ha_url and resolved_settings.ha_token:
        from packages.pipelines.ha_bridge import HaBridgeWorker
        ha_bridge = HaBridgeWorker(
            transformation_service.ingest_ha_states,
            ha_url=resolved_settings.ha_url,
            ha_token=resolved_settings.ha_token,
        )

    return create_app(
        container,
        transformation_service=transformation_service,
        reporting_service=reporting_service,
        session_manager=build_session_manager(resolved_settings),
        oidc_provider=build_oidc_provider(resolved_settings),
        auth_failure_window_seconds=resolved_settings.auth_failure_window_seconds,
        auth_failure_threshold=resolved_settings.auth_failure_threshold,
        auth_lockout_seconds=resolved_settings.auth_lockout_seconds,
        enable_unsafe_admin=resolved_settings.enable_unsafe_admin,
        external_registry_cache_root=resolved_settings.resolved_external_registry_cache_root,
        ha_bridge=ha_bridge,
    )


def main() -> int:
    settings = AppSettings.from_env()
    configure_logging()
    logger = logging.getLogger("homelab_analytics.api")
    try:
        app = build_app(settings)
    except ValueError as exc:
        logger.error(
            "api startup configuration invalid",
            extra={"auth_mode": settings.auth_mode, "error": str(exc)},
        )
        return 1
    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
