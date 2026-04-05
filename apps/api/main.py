from __future__ import annotations

import logging

import uvicorn

from apps import runtime_support as _runtime_support
from apps.api.app import create_app
from apps.api.ha_startup import (
    build_ha_startup_runtime,
)
from packages.domains.finance.manifest import FINANCE_PACK
from packages.domains.homelab.manifest import HOMELAB_PACK
from packages.domains.overview.manifest import OVERVIEW_PACK
from packages.domains.utilities.manifest import UTILITIES_PACK
from packages.pipelines.reporting_service import ReportingAccessMode
from packages.platform.auth.configuration import validate_auth_configuration
from packages.platform.auth.machine_jwt_provider import build_machine_jwt_provider
from packages.platform.auth.oidc_provider import build_oidc_provider
from packages.platform.auth.proxy_provider import build_proxy_provider
from packages.platform.auth.session_manager import build_session_manager
from packages.platform.runtime.builder import build_container
from packages.shared.logging import configure_logging
from packages.shared.settings import AppSettings

build_extension_registry = _runtime_support.build_extension_registry
build_function_registry = _runtime_support.build_function_registry
build_lazy_transformation_service = _runtime_support.build_lazy_transformation_service
build_service = _runtime_support.build_service
build_transformation_service = _runtime_support.build_transformation_service


def _build_reporting_service(
    settings: AppSettings,
    transformation_service,
    extension_registry=None,
    control_plane_store=None,
    *,
    access_mode: ReportingAccessMode | None = None,
):
    resolved_access_mode = access_mode
    if resolved_access_mode is None:
        resolved_access_mode = (
            ReportingAccessMode.PUBLISHED
            if settings.reporting_backend.lower() == "postgres"
            else ReportingAccessMode.WAREHOUSE
        )
    return _runtime_support.build_reporting_service(
        settings,
        transformation_service,
        extension_registry,
        control_plane_store,
        access_mode=resolved_access_mode,
    )


build_reporting_service = _build_reporting_service


def _build_api_startup_components(
    settings: AppSettings,
):
    capability_packs = [FINANCE_PACK, UTILITIES_PACK, OVERVIEW_PACK, HOMELAB_PACK]
    container = build_container(
        settings,
        capability_packs=capability_packs,
    )
    service = build_service(
        settings,
        metadata_repository=container.run_metadata_store,
        blob_store=container.blob_store,
    )
    subscription_service = _runtime_support.build_subscription_service(
        settings,
        metadata_repository=container.run_metadata_store,
        blob_store=container.blob_store,
    )
    contract_price_service = _runtime_support.build_contract_price_service(
        settings,
        metadata_repository=container.run_metadata_store,
        blob_store=container.blob_store,
    )
    transformation_service = build_lazy_transformation_service(
        settings, container=container
    )
    reporting_service = build_reporting_service(
        settings,
        transformation_service,
        container.extension_registry,
        container.control_plane_store,
        access_mode=(
            ReportingAccessMode.PUBLISHED
            if settings.reporting_backend.lower() == "postgres"
            else ReportingAccessMode.WAREHOUSE
        ),
    )
    ha_runtime = build_ha_startup_runtime(
        settings,
        transformation_service=transformation_service,
        reporting_service=reporting_service,
        capability_packs=capability_packs,
    )
    return (
        container,
        service,
        subscription_service,
        contract_price_service,
        transformation_service,
        reporting_service,
        ha_runtime,
    )


def build_app(settings: AppSettings | None = None):
    resolved_settings = settings or AppSettings.from_env()
    validate_auth_configuration(resolved_settings)

    (
        container,
        service,
        subscription_service,
        contract_price_service,
        transformation_service,
        reporting_service,
        ha_runtime,
    ) = _build_api_startup_components(resolved_settings)

    return create_app(
        container,
        account_transaction_service=service,
        transformation_service=transformation_service,
        reporting_service=reporting_service,
        subscription_service=subscription_service,
        contract_price_service=contract_price_service,
        session_manager=build_session_manager(resolved_settings),
        oidc_provider=build_oidc_provider(resolved_settings),
        machine_jwt_provider=build_machine_jwt_provider(resolved_settings),
        proxy_provider=build_proxy_provider(resolved_settings),
        auth_failure_window_seconds=resolved_settings.auth_failure_window_seconds,
        auth_failure_threshold=resolved_settings.auth_failure_threshold,
        auth_lockout_seconds=resolved_settings.auth_lockout_seconds,
        enable_unsafe_admin=resolved_settings.enable_unsafe_admin,
        external_registry_cache_root=resolved_settings.resolved_external_registry_cache_root,
        ha_bridge=ha_runtime.bridge,
        ha_mqtt_publisher=ha_runtime.mqtt_publisher,
        ha_policy_evaluator=ha_runtime.policy_evaluator,
        ha_action_dispatcher=ha_runtime.action_dispatcher,
        ha_action_proposal_registry=ha_runtime.action_proposal_registry,
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
            extra={
                "identity_mode": settings.resolved_identity_mode,
                "error": str(exc),
            },
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
