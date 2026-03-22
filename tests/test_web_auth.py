from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = ROOT / "apps" / "web" / "frontend"


def test_nextjs_frontend_exposes_login_and_logout_routes() -> None:
    login_route = (FRONTEND_ROOT / "app" / "auth" / "login" / "route.js").read_text()
    callback_route = (
        FRONTEND_ROOT / "app" / "auth" / "callback" / "route.js"
    ).read_text()
    logout_route = (FRONTEND_ROOT / "app" / "auth" / "logout" / "route.js").read_text()
    ready_route = (FRONTEND_ROOT / "app" / "ready" / "route.js").read_text()
    login_page = (FRONTEND_ROOT / "app" / "login" / "page.js").read_text()
    control_page = (FRONTEND_ROOT / "app" / "control" / "page.js").read_text()
    service_token_route = (
        FRONTEND_ROOT / "app" / "control" / "service-tokens" / "route.js"
    ).read_text()
    service_token_revoke_route = (
        FRONTEND_ROOT
        / "app"
        / "control"
        / "service-tokens"
        / "[tokenId]"
        / "revoke"
        / "route.js"
    ).read_text()
    service_token_panel = (
        FRONTEND_ROOT / "components" / "service-token-panel.js"
    ).read_text()
    control_catalog_page = (
        FRONTEND_ROOT / "app" / "control" / "catalog" / "page.js"
    ).read_text()
    external_registry_panel = (
        FRONTEND_ROOT / "components" / "external-registry-panel.js"
    ).read_text()
    function_catalog_panel = (
        FRONTEND_ROOT / "components" / "function-catalog-panel.js"
    ).read_text()
    transformation_catalog_panel = (
        FRONTEND_ROOT / "components" / "transformation-catalog-panel.js"
    ).read_text()
    config_spec = (FRONTEND_ROOT / "lib" / "config-spec.js").read_text()
    dataset_contract_route = (
        FRONTEND_ROOT / "app" / "control" / "catalog" / "dataset-contracts" / "route.js"
    ).read_text()
    dataset_contract_archive_route = (
        FRONTEND_ROOT
        / "app"
        / "control"
        / "catalog"
        / "dataset-contracts"
        / "[datasetContractId]"
        / "archive"
        / "route.js"
    ).read_text()
    column_mapping_route = (
        FRONTEND_ROOT / "app" / "control" / "catalog" / "column-mappings" / "route.js"
    ).read_text()
    column_mapping_archive_route = (
        FRONTEND_ROOT
        / "app"
        / "control"
        / "catalog"
        / "column-mappings"
        / "[columnMappingId]"
        / "archive"
        / "route.js"
    ).read_text()
    preview_route = (
        FRONTEND_ROOT / "app" / "control" / "catalog" / "preview" / "route.js"
    ).read_text()
    control_execution_page = (
        FRONTEND_ROOT / "app" / "control" / "execution" / "page.js"
    ).read_text()
    upload_page = (FRONTEND_ROOT / "app" / "upload" / "page.js").read_text()
    upload_account_route = (
        FRONTEND_ROOT / "app" / "upload" / "account-transactions" / "route.js"
    ).read_text()
    upload_subscription_route = (
        FRONTEND_ROOT / "app" / "upload" / "subscriptions" / "route.js"
    ).read_text()
    upload_contract_price_route = (
        FRONTEND_ROOT / "app" / "upload" / "contract-prices" / "route.js"
    ).read_text()
    upload_configured_route = (
        FRONTEND_ROOT / "app" / "upload" / "configured-csv" / "route.js"
    ).read_text()
    mapping_preview_component = (
        FRONTEND_ROOT / "components" / "mapping-preview-panel.js"
    ).read_text()
    source_system_route = (
        FRONTEND_ROOT / "app" / "control" / "catalog" / "source-systems" / "route.js"
    ).read_text()
    source_system_update_route = (
        FRONTEND_ROOT
        / "app"
        / "control"
        / "catalog"
        / "source-systems"
        / "[sourceSystemId]"
        / "route.js"
    ).read_text()
    source_asset_route = (
        FRONTEND_ROOT / "app" / "control" / "catalog" / "source-assets" / "route.js"
    ).read_text()
    source_asset_update_route = (
        FRONTEND_ROOT
        / "app"
        / "control"
        / "catalog"
        / "source-assets"
        / "[sourceAssetId]"
        / "route.js"
    ).read_text()
    source_asset_archive_route = (
        FRONTEND_ROOT
        / "app"
        / "control"
        / "catalog"
        / "source-assets"
        / "[sourceAssetId]"
        / "archive"
        / "route.js"
    ).read_text()
    source_asset_delete_route = (
        FRONTEND_ROOT
        / "app"
        / "control"
        / "catalog"
        / "source-assets"
        / "[sourceAssetId]"
        / "delete"
        / "route.js"
    ).read_text()
    extension_registry_source_route = (
        FRONTEND_ROOT
        / "app"
        / "control"
        / "catalog"
        / "extension-registry-sources"
        / "route.js"
    ).read_text()
    extension_registry_source_update_route = (
        FRONTEND_ROOT
        / "app"
        / "control"
        / "catalog"
        / "extension-registry-sources"
        / "[extensionRegistrySourceId]"
        / "route.js"
    ).read_text()
    extension_registry_source_archive_route = (
        FRONTEND_ROOT
        / "app"
        / "control"
        / "catalog"
        / "extension-registry-sources"
        / "[extensionRegistrySourceId]"
        / "archive"
        / "route.js"
    ).read_text()
    extension_registry_source_sync_route = (
        FRONTEND_ROOT
        / "app"
        / "control"
        / "catalog"
        / "extension-registry-sources"
        / "[extensionRegistrySourceId]"
        / "sync"
        / "route.js"
    ).read_text()
    extension_registry_source_activate_route = (
        FRONTEND_ROOT
        / "app"
        / "control"
        / "catalog"
        / "extension-registry-sources"
        / "[extensionRegistrySourceId]"
        / "activate"
        / "route.js"
    ).read_text()
    transformation_package_route = (
        FRONTEND_ROOT
        / "app"
        / "control"
        / "catalog"
        / "transformation-packages"
        / "route.js"
    ).read_text()
    transformation_package_update_route = (
        FRONTEND_ROOT
        / "app"
        / "control"
        / "catalog"
        / "transformation-packages"
        / "[transformationPackageId]"
        / "route.js"
    ).read_text()
    transformation_package_archive_route = (
        FRONTEND_ROOT
        / "app"
        / "control"
        / "catalog"
        / "transformation-packages"
        / "[transformationPackageId]"
        / "archive"
        / "route.js"
    ).read_text()
    publication_definition_route = (
        FRONTEND_ROOT
        / "app"
        / "control"
        / "catalog"
        / "publication-definitions"
        / "route.js"
    ).read_text()
    publication_definition_update_route = (
        FRONTEND_ROOT
        / "app"
        / "control"
        / "catalog"
        / "publication-definitions"
        / "[publicationDefinitionId]"
        / "route.js"
    ).read_text()
    publication_definition_archive_route = (
        FRONTEND_ROOT
        / "app"
        / "control"
        / "catalog"
        / "publication-definitions"
        / "[publicationDefinitionId]"
        / "archive"
        / "route.js"
    ).read_text()
    ingestion_definition_route = (
        FRONTEND_ROOT
        / "app"
        / "control"
        / "execution"
        / "ingestion-definitions"
        / "route.js"
    ).read_text()
    ingestion_definition_update_route = (
        FRONTEND_ROOT
        / "app"
        / "control"
        / "execution"
        / "ingestion-definitions"
        / "[ingestionDefinitionId]"
        / "route.js"
    ).read_text()
    ingestion_definition_archive_route = (
        FRONTEND_ROOT
        / "app"
        / "control"
        / "execution"
        / "ingestion-definitions"
        / "[ingestionDefinitionId]"
        / "archive"
        / "route.js"
    ).read_text()
    ingestion_definition_delete_route = (
        FRONTEND_ROOT
        / "app"
        / "control"
        / "execution"
        / "ingestion-definitions"
        / "[ingestionDefinitionId]"
        / "delete"
        / "route.js"
    ).read_text()
    process_definition_route = (
        FRONTEND_ROOT
        / "app"
        / "control"
        / "execution"
        / "ingestion-definitions"
        / "[ingestionDefinitionId]"
        / "process"
        / "route.js"
    ).read_text()
    execution_schedule_route = (
        FRONTEND_ROOT
        / "app"
        / "control"
        / "execution"
        / "execution-schedules"
        / "route.js"
    ).read_text()
    execution_schedule_update_route = (
        FRONTEND_ROOT
        / "app"
        / "control"
        / "execution"
        / "execution-schedules"
        / "[scheduleId]"
        / "route.js"
    ).read_text()
    execution_schedule_archive_route = (
        FRONTEND_ROOT
        / "app"
        / "control"
        / "execution"
        / "execution-schedules"
        / "[scheduleId]"
        / "archive"
        / "route.js"
    ).read_text()
    execution_schedule_delete_route = (
        FRONTEND_ROOT
        / "app"
        / "control"
        / "execution"
        / "execution-schedules"
        / "[scheduleId]"
        / "delete"
        / "route.js"
    ).read_text()
    schedule_dispatch_route = (
        FRONTEND_ROOT
        / "app"
        / "control"
        / "execution"
        / "schedule-dispatches"
        / "route.js"
    ).read_text()
    dispatch_detail_page = (
        FRONTEND_ROOT
        / "app"
        / "control"
        / "execution"
        / "dispatches"
        / "[dispatchId]"
        / "page.js"
    ).read_text()
    dispatch_retry_route = (
        FRONTEND_ROOT
        / "app"
        / "control"
        / "execution"
        / "dispatches"
        / "[dispatchId]"
        / "retry"
        / "route.js"
    ).read_text()
    run_detail_page = (
        FRONTEND_ROOT / "app" / "runs" / "[runId]" / "page.js"
    ).read_text()
    run_retry_route = (
        FRONTEND_ROOT / "app" / "runs" / "[runId]" / "retry" / "route.js"
    ).read_text()

    assert "// @ts-check" in login_route
    assert 'backendRequest("get", "/auth/login"' in login_route
    assert 'backendRequest("get", "/auth/callback"' in callback_route
    assert "copyBackendSetCookies" in callback_route
    assert "copyBackendSetCookies" in login_route
    assert 'backendRequest("post", "/auth/logout"' in logout_route
    assert 'status: "ready"' in ready_route
    assert "auth_mode" not in ready_route
    assert "HOMELAB_ANALYTICS_IDENTITY_MODE" in ready_route
    assert "Sign In" in login_page
    assert 'action="/auth/login"' in login_page
    assert "Too many failed login attempts" in login_page
    assert "Sign In with OIDC" in login_page
    assert "Proxy-Managed Sign-In" in login_page
    assert 'process.env.HOMELAB_ANALYTICS_IDENTITY_MODE' in login_page
    assert "getLocalUsers" in control_page
    assert "getAuthAuditEvents" in control_page
    assert "getOperationalSummary" in control_page
    assert "getServiceTokens" in control_page
    assert "ServiceTokenPanel" in control_page
    assert 'backendJsonRequest("post", "/auth/service-tokens"' in service_token_route
    assert "/auth/service-tokens/{token_id}/revoke" in service_token_revoke_route
    assert 'fetch("/control/service-tokens"' in service_token_panel
    assert "Copy once" in service_token_panel
    assert "expiring soon" in service_token_panel
    assert "getSourceSystems" in control_catalog_page
    assert "getSourceAssets" in control_catalog_page
    assert "getOperationalSummary" in control_catalog_page
    assert "getDatasetContractDiff" in control_catalog_page
    assert "getColumnMappingDiff" in control_catalog_page
    assert "getExtensionRegistrySources" in control_catalog_page
    assert "getExtensionRegistryRevisions" in control_catalog_page
    assert "getExtensionRegistryActivations" in control_catalog_page
    assert "getFunctions" in control_catalog_page
    assert "getTransformationHandlers" in control_catalog_page
    assert "getPublicationKeys" in control_catalog_page
    assert "getPublicationDefinitions" in control_catalog_page
    assert "MappingPreviewPanel" in control_catalog_page
    assert "Create dataset contract version" in control_catalog_page
    assert "Create column mapping version" in control_catalog_page
    assert "ExternalRegistryPanel" in control_catalog_page
    assert "FunctionCatalogPanel" in control_catalog_page
    assert "TransformationCatalogPanel" in control_catalog_page
    assert "parseColumnsSpec" in dataset_contract_route
    assert "/config/dataset-contracts" in dataset_contract_route
    assert '"/config/dataset-contracts/{dataset_contract_id}/archive"' in dataset_contract_archive_route
    assert "parseRulesSpec" in column_mapping_route
    assert "function_key" in config_spec
    assert "/config/column-mappings" in column_mapping_route
    assert '"/config/column-mappings/{column_mapping_id}/archive"' in column_mapping_archive_route
    assert "Create external registry source" in external_registry_panel
    assert "External registry sources" in external_registry_panel
    assert "Sync and activate" in external_registry_panel
    assert "Activate revision" in external_registry_panel
    assert "Custom functions" in function_catalog_panel
    assert "function_key" in function_catalog_panel
    assert "Create transformation package" in transformation_catalog_panel
    assert "Create publication definition" in transformation_catalog_panel
    assert "Available transformation handlers" in transformation_catalog_panel
    assert "Available publication keys" in transformation_catalog_panel
    assert "Archive package" in transformation_catalog_panel
    assert "Archive publication" in transformation_catalog_panel
    assert "backendJsonRequest" in preview_route
    assert '"/config/column-mappings/preview"' in preview_route
    assert "getIngestionDefinitions" in control_execution_page
    assert "getExecutionSchedules" in control_execution_page
    assert "getOperationalSummary" in control_execution_page
    assert "Recovered stale dispatches" in control_execution_page
    assert "Worker heartbeats" in control_execution_page
    assert "Stale running dispatches" in control_execution_page
    assert "Manual Uploads" in upload_page
    assert 'action="/upload/account-transactions"' in upload_page
    assert 'action="/upload/configured-csv"' in upload_page
    assert "proxyUploadRequest" in upload_account_route
    assert 'backendPath: "/ingest/account-transactions"' in upload_account_route
    assert 'backendPath: "/ingest/subscriptions"' in upload_subscription_route
    assert 'backendPath: "/ingest/contract-prices"' in upload_contract_price_route
    assert 'backendPath: "/ingest/configured-csv"' in upload_configured_route
    assert 'fetch("/control/catalog/preview"' in mapping_preview_component
    assert "getRun" in run_detail_page
    assert 'backendRequest("post", "/config/source-systems"' in source_system_route
    assert '"/config/source-systems/{source_system_id}"' in source_system_update_route
    assert 'backendRequest("post", "/config/source-assets"' in source_asset_route
    assert '"/config/source-assets/{source_asset_id}"' in source_asset_update_route
    assert '"/config/source-assets/{source_asset_id}/archive"' in source_asset_archive_route
    assert '"/config/source-assets/{source_asset_id}"' in source_asset_delete_route
    assert 'backendRequest("post", "/config/extension-registry-sources"' in extension_registry_source_route
    assert '"/config/extension-registry-sources/{extension_registry_source_id}"' in extension_registry_source_update_route
    assert '"/config/extension-registry-sources/{extension_registry_source_id}/archive"' in extension_registry_source_archive_route
    assert '"/config/extension-registry-sources/{extension_registry_source_id}/sync"' in extension_registry_source_sync_route
    assert '"/config/extension-registry-sources/{extension_registry_source_id}/activate"' in extension_registry_source_activate_route
    assert 'backendRequest("post", "/config/transformation-packages"' in transformation_package_route
    assert '"/config/transformation-packages/{transformation_package_id}"' in transformation_package_update_route
    assert '"/config/transformation-packages/{transformation_package_id}/archive"' in transformation_package_archive_route
    assert 'backendRequest("post", "/config/publication-definitions"' in publication_definition_route
    assert '"/config/publication-definitions/{publication_definition_id}"' in publication_definition_update_route
    assert '"/config/publication-definitions/{publication_definition_id}/archive"' in publication_definition_archive_route
    assert 'backendRequest("post", "/config/ingestion-definitions"' in ingestion_definition_route
    assert '"/config/ingestion-definitions/{ingestion_definition_id}"' in ingestion_definition_update_route
    assert '"/config/ingestion-definitions/{ingestion_definition_id}/archive"' in ingestion_definition_archive_route
    assert '"/config/ingestion-definitions/{ingestion_definition_id}"' in ingestion_definition_delete_route
    assert 'backendRequest("post", "/config/execution-schedules"' in execution_schedule_route
    assert '"/config/execution-schedules/{schedule_id}"' in execution_schedule_update_route
    assert '"/config/execution-schedules/{schedule_id}/archive"' in execution_schedule_archive_route
    assert '"/config/execution-schedules/{schedule_id}"' in execution_schedule_delete_route
    assert 'backendRequest("post", "/control/schedule-dispatches"' in schedule_dispatch_route
    assert "getScheduleDispatch" in dispatch_detail_page
    assert "getOperationalSummary" in dispatch_detail_page
    assert "Requeue dispatch" in dispatch_detail_page
    assert "Claim expires" in dispatch_detail_page
    assert "Failure reason" in dispatch_detail_page
    assert "Worker detail" in dispatch_detail_page
    assert '"/control/schedule-dispatches/{dispatch_id}/retry"' in dispatch_retry_route
    assert '"/ingest/ingestion-definitions/{ingestion_definition_id}/process"' in process_definition_route
    assert 'backendJsonRequest("post", "/runs/{run_id}/retry"' in run_retry_route
    assert "Retry run" in run_detail_page


def test_nextjs_frontend_reads_data_from_api_helper_only() -> None:
    dashboard_source = (FRONTEND_ROOT / "app" / "page.js").read_text()
    homelab_source = (FRONTEND_ROOT / "app" / "homelab" / "page.js").read_text()
    runs_source = (FRONTEND_ROOT / "app" / "runs" / "page.js").read_text()
    reports_source = (FRONTEND_ROOT / "app" / "reports" / "page.js").read_text()
    control_source = (FRONTEND_ROOT / "app" / "control" / "page.js").read_text()
    control_catalog_source = (
        FRONTEND_ROOT / "app" / "control" / "catalog" / "page.js"
    ).read_text()
    upload_source = (FRONTEND_ROOT / "app" / "upload" / "page.js").read_text()
    control_execution_source = (
        FRONTEND_ROOT / "app" / "control" / "execution" / "page.js"
    ).read_text()
    run_detail_source = (
        FRONTEND_ROOT / "app" / "runs" / "[runId]" / "page.js"
    ).read_text()
    dispatch_detail_source = (
        FRONTEND_ROOT
        / "app"
        / "control"
        / "execution"
        / "dispatches"
        / "[dispatchId]"
        / "page.js"
    ).read_text()
    backend_source = (FRONTEND_ROOT / "lib" / "backend.ts").read_text()
    renderer_discovery_source = (
        FRONTEND_ROOT / "lib" / "renderer-discovery.ts"
    ).read_text()
    upload_route_helper = (FRONTEND_ROOT / "lib" / "upload-route.js").read_text()

    assert "HOMELAB_ANALYTICS_API_BASE_URL" in backend_source
    assert 'fetch(`${getApiBaseUrl()}${path}`' in backend_source
    assert 'outboundHeaders.set("x-csrf-token", csrfToken)' in backend_source
    assert "Promise<any>" not in backend_source
    assert "as any" not in backend_source
    assert "getSourceSystems" in backend_source
    assert "getSourceAssets" in backend_source
    assert "getDatasetContracts" in backend_source
    assert "getColumnMappings" in backend_source
    assert "getTransformationHandlers" in backend_source
    assert "getPublicationKeys" in backend_source
    assert "getExtensionRegistrySources" in backend_source
    assert "getExtensionRegistryRevisions" in backend_source
    assert "getExtensionRegistryActivations" in backend_source
    assert "getFunctions" in backend_source
    assert "getPublicationDefinitions" in backend_source
    assert "getIngestionDefinitions" in backend_source
    assert "getExecutionSchedules" in backend_source
    assert "getServiceTokens" in backend_source
    assert "getOperationalSummary" in backend_source
    assert "getScheduleDispatch" in backend_source
    assert "getDatasetContractDiff" in backend_source
    assert "getColumnMappingDiff" in backend_source
    assert "getRunsPage" in backend_source
    assert "getRun" in backend_source
    assert "getTransformationAudit" in backend_source
    assert "getPublicationContracts" in backend_source
    assert "getUiDescriptors" in backend_source
    assert "getPublicationContracts()" in renderer_discovery_source
    assert "getUiDescriptors()" in renderer_discovery_source
    assert "renderer_hints.web_surface" in renderer_discovery_source
    assert "generated/publication-contracts" not in renderer_discovery_source
    assert "getMonthlyCashflow" in dashboard_source
    assert "getRuns" in dashboard_source
    assert "getRunsPage" in runs_source
    assert "getMonthlyCashflow" in reports_source
    assert "getWebRendererDiscovery" in reports_source
    assert "RendererDiscovery" in reports_source
    assert "getWebRendererDiscovery" in homelab_source
    assert "RendererDiscovery" in homelab_source
    assert "getLocalUsers" in control_source
    assert "getSourceSystems" in control_catalog_source
    assert "getDatasetContracts({ includeArchived: true })" in control_catalog_source
    assert "getColumnMappings({ includeArchived: true })" in control_catalog_source
    assert "getTransformationHandlers()" in control_catalog_source
    assert "getPublicationKeys()" in control_catalog_source
    assert "getExtensionRegistrySources({ includeArchived: true })" in control_catalog_source
    assert "getExtensionRegistryRevisions()" in control_catalog_source
    assert "getExtensionRegistryActivations()" in control_catalog_source
    assert "getFunctions()" in control_catalog_source
    assert "getPublicationDefinitions({ includeArchived: true })" in control_catalog_source
    assert "getOperationalSummary" in control_catalog_source
    assert "getSourceAssets({ includeArchived: true })" in upload_source
    assert "backendRequest(backendPath" in upload_route_helper
    assert "encodeUploadFeedback" in upload_route_helper
    assert "parseFeedback" in upload_source
    assert "getIngestionDefinitions" in control_execution_source
    assert "getSourceAssets({ includeArchived: true })" in control_execution_source
    assert "getExecutionSchedules({ includeArchived: true })" in control_execution_source
    assert "getOperationalSummary" in control_execution_source
    assert "getRun" in run_detail_source
    assert "getSourceLineage" in run_detail_source
    assert "getPublicationAudit" in run_detail_source
    assert "getScheduleDispatch" in dispatch_detail_source
    assert "ReportingService(" not in dashboard_source


def test_nextjs_frontend_centralizes_raw_backend_transport() -> None:
    backend_boundary = FRONTEND_ROOT / "lib" / "backend.ts"
    transport_markers = (
        'fetch(`${getApiBaseUrl()}${path}`',
        "createClient<paths>",
        "HOMELAB_ANALYTICS_API_BASE_URL",
    )
    source_suffixes = {".js", ".jsx", ".ts", ".tsx"}

    for source_path in FRONTEND_ROOT.rglob("*"):
        if (
            not source_path.is_file()
            or source_path.suffix not in source_suffixes
            or source_path == backend_boundary
            or "generated" in source_path.parts
            or ".next" in source_path.parts
            or "node_modules" in source_path.parts
        ):
            continue
        source = source_path.read_text()
        for marker in transport_markers:
            assert marker not in source, f"{source_path} should not contain {marker!r}"


def test_nextjs_frontend_uses_typed_contract_mutation_helpers() -> None:
    allowed_raw_routes = {
        FRONTEND_ROOT / "app" / "upload" / "ha-states" / "route.js",
    }

    for route_path in FRONTEND_ROOT.rglob("route.js"):
        source = route_path.read_text()
        if route_path in allowed_raw_routes:
            continue
        if "backendRequest(" not in source and "backendJsonRequest(" not in source:
            continue
        assert "// @ts-check" in source, f"{route_path} should opt into JS type-checking"
        assert 'backendRequest("/' not in source, f"{route_path} should use literal typed method/path helpers"
        assert 'method: "' not in source, f"{route_path} should not pass raw HTTP methods"
        assert 'contentType: "application/json"' not in source, (
            f"{route_path} should rely on typed JSON serialization"
        )
        assert "JSON.stringify(" not in source, (
            f"{route_path} should not hand-serialize JSON bodies"
        )
