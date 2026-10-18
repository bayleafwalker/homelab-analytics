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
    # RP-initiated logout: follow the backend's end_session_url (http(s) only),
    # otherwise fall back to the local login page; session cookies are cleared
    # on the redirect either way.
    assert "end_session_url" in logout_route
    assert 'url.protocol === "https:" || url.protocol === "http:"' in logout_route
    assert 'new URL("/login", request.url)' in logout_route
    assert "copyBackendSetCookies(response, redirectResponse.headers)" in logout_route
    assert 'status: "ready"' in ready_route
    assert "auth_mode" not in ready_route
    assert "HOMELAB_ANALYTICS_IDENTITY_MODE" in ready_route
    assert "Sign In" in login_page
    assert 'action="/auth/login"' in login_page
    assert "Too many failed login attempts" in login_page
    assert "Sign In with OIDC" in login_page
    assert "Proxy-Managed Sign-In" in login_page
    assert "authMode" not in login_page
    assert 'if (error && identityMode === "oidc")' not in login_page
    assert "Single sign-on failed. Try again or contact an administrator." in login_page
    assert "Your OIDC identity is valid but not mapped to an application role." in login_page
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
    assert 'backendPath: "/ingest/configured-csv"' in upload_subscription_route
    assert 'upload_path: "/upload/subscriptions"' in upload_subscription_route
    assert 'backendPath: "/ingest/configured-csv"' in upload_contract_price_route
    assert 'upload_path: "/upload/contract-prices"' in upload_contract_price_route
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
    assert 'createScheduleDispatchHandler({ basePath: "/control/execution" })' in (
        schedule_dispatch_route
    )
    assert "getScheduleDispatch" in dispatch_detail_page
    assert "getOperationalSummary" in dispatch_detail_page
    assert "Requeue dispatch" in dispatch_detail_page
    assert "Claim expires" in dispatch_detail_page
    assert "Failure reason" in dispatch_detail_page
    assert "Worker detail" in dispatch_detail_page
    assert "createScheduleDispatchRetryHandler" in dispatch_retry_route
    assert '"/ingest/ingestion-definitions/{ingestion_definition_id}/process"' in process_definition_route
    assert 'backendJsonRequest("post", "/runs/{run_id}/retry"' in run_retry_route
    assert "Retry run" in run_detail_page


def test_nextjs_frontend_reads_data_from_api_helper_only() -> None:
    dashboard_source = (FRONTEND_ROOT / "app" / "page.js").read_text()
    homelab_source = (FRONTEND_ROOT / "app" / "homelab" / "page.js").read_text()
    homelab_cost_benefit_panel_source = (
        FRONTEND_ROOT / "components" / "homelab-cost-benefit-panel.js"
    ).read_text()
    homelab_approve_route = (
        FRONTEND_ROOT
        / "app"
        / "homelab"
        / "actions"
        / "proposals"
        / "[actionId]"
        / "approve"
        / "route.js"
    ).read_text()
    homelab_dismiss_route = (
        FRONTEND_ROOT
        / "app"
        / "homelab"
        / "actions"
        / "proposals"
        / "[actionId]"
        / "dismiss"
        / "route.js"
    ).read_text()
    costs_source = (FRONTEND_ROOT / "app" / "costs" / "page.js").read_text()
    tariff_shock_panel_source = (
        FRONTEND_ROOT / "components" / "tariff-shock-panel.js"
    ).read_text()
    scenarios_source = (FRONTEND_ROOT / "app" / "scenarios" / "page.js").read_text()
    scenarios_compare_source = (
        FRONTEND_ROOT / "app" / "scenarios" / "compare" / "page.js"
    ).read_text()
    scenario_compare_sets_source = (
        FRONTEND_ROOT / "components" / "saved-scenario-compare-sets.js"
    ).read_text()
    scenario_detail_source = (
        FRONTEND_ROOT / "app" / "scenarios" / "[scenarioId]" / "page.js"
    ).read_text()
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
    control_freshness_source = (
        FRONTEND_ROOT / "app" / "control" / "freshness" / "page.js"
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
    assert "getHaActionProposals" in backend_source
    assert "getHomelabServices" in backend_source
    assert "getHomelabWorkloads" in backend_source
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
    assert "TariffShockPanel" in costs_source
    assert "getWebRendererDiscovery" in homelab_source
    assert "RendererDiscovery" in homelab_source
    assert "getHaActionProposals" in homelab_source
    assert "getHomelabRoi" in homelab_source
    assert "getHomelabWorkloads" in homelab_source
    assert "Value Loop" in homelab_source
    assert "formatPercent" in homelab_source
    assert "formatRatio" in homelab_source
    assert "HomelabCostBenefitPanel" in homelab_source
    assert "Healthy service share" in homelab_source
    assert "Cost per healthy service" in homelab_source
    assert "Cost per tracked workload" in homelab_source
    assert "ROI score" in homelab_source
    assert "Highest-cost share" in homelab_source
    assert "/api/scenarios/homelab-cost-benefit" in homelab_cost_benefit_panel_source
    assert "/api/scenarios/${data.scenario_id}/comparison" in homelab_cost_benefit_panel_source
    assert "/api/scenarios/compare-sets" in homelab_cost_benefit_panel_source
    assert "monthly_cost_delta" in homelab_cost_benefit_panel_source
    assert "Homelab cost/benefit" in homelab_cost_benefit_panel_source
    assert "View scenario" in homelab_cost_benefit_panel_source
    assert "Compare scenarios" in homelab_cost_benefit_panel_source
    assert "Save compare set" in homelab_cost_benefit_panel_source
    assert "/api/scenarios" in homelab_cost_benefit_panel_source
    assert "/scenarios/compare?left=" in homelab_cost_benefit_panel_source
    assert "&right=" in homelab_cost_benefit_panel_source
    assert "Cost/value summary" in homelab_cost_benefit_panel_source
    assert "comparison?.summary_rows?.length > 0" in homelab_cost_benefit_panel_source
    assert "Assumptions" in homelab_cost_benefit_panel_source
    assert "Approval queue" in homelab_source
    assert "Approve" in homelab_source
    assert "Dismiss" in homelab_source
    assert "approval-approved" in homelab_source
    assert "approval-dismissed" in homelab_source
    assert "/api/scenarios/tariff-shock" in tariff_shock_panel_source
    assert "tariff_pct_delta" in tariff_shock_panel_source
    assert "Tariff shock what-if" in tariff_shock_panel_source
    assert "/scenarios/${result.scenario_id}" in homelab_cost_benefit_panel_source
    assert "homelab_cost_benefit" in scenarios_source
    assert "Homelab cost/benefit" in scenarios_source
    assert "/scenarios/compare" in scenarios_source
    assert "Compare saved scenarios" in scenarios_source
    assert "getScenarioCompareSets({ includeArchived: true })" in scenarios_compare_source
    assert "Compare scenarios" in scenarios_compare_source
    assert "Saved compare shortcuts" in scenario_compare_sets_source
    assert "Shared compare sets" in scenario_compare_sets_source
    assert "Show archived compare sets" in scenario_compare_sets_source
    assert "Rename compare set" in scenario_compare_sets_source
    assert "Restore compare set" in scenario_compare_sets_source
    assert "Archive compare set" in scenario_compare_sets_source
    assert "Open compare set" in scenario_compare_sets_source
    assert "/api/scenarios/compare-sets" in scenario_compare_sets_source
    assert "/restore" in scenario_compare_sets_source
    assert "Pick two different scenarios to compare" in scenarios_compare_source
    assert 'name="left"' in scenarios_compare_source
    assert 'name="right"' in scenarios_compare_source
    assert "summary_rows" in scenario_detail_source
    assert "Cost/value summary" in scenario_detail_source
    assert "Compare scenarios" in scenario_detail_source
    assert "/scenarios/compare?left=" in scenario_detail_source
    assert "/api/ha/actions/proposals/{action_id}/approve" in homelab_approve_route
    assert "/api/ha/actions/proposals/{action_id}/dismiss" in homelab_dismiss_route
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
    assert "getRuns(200)" in control_freshness_source
    assert "nextActionFor" in control_freshness_source
    assert "Next action" in control_freshness_source
    assert "Upload first file" in control_freshness_source
    assert "Open failed run" in control_freshness_source
    assert "Upload next export" in control_freshness_source
    assert "Review schedule" in control_freshness_source
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


def test_nextjs_frontend_exposes_parallel_retro_shell_and_terminal_boundary() -> None:
    app_shell_source = (FRONTEND_ROOT / "components" / "app-shell.js").read_text()
    retro_layout_source = (FRONTEND_ROOT / "app" / "retro" / "layout.js").read_text()
    retro_page_source = (FRONTEND_ROOT / "app" / "retro" / "page.js").read_text()
    retro_control_source = (
        FRONTEND_ROOT / "app" / "retro" / "control" / "page.js"
    ).read_text()
    retro_catalog_source = (
        FRONTEND_ROOT / "app" / "retro" / "control" / "catalog" / "page.js"
    ).read_text()
    retro_execution_source = (
        FRONTEND_ROOT / "app" / "retro" / "control" / "execution" / "page.js"
    ).read_text()
    retro_money_source = (
        FRONTEND_ROOT / "app" / "retro" / "money" / "page.js"
    ).read_text()
    retro_terminal_source = (
        FRONTEND_ROOT / "app" / "retro" / "terminal" / "page.js"
    ).read_text()
    retro_utilities_source = (
        FRONTEND_ROOT / "app" / "retro" / "utilities" / "page.js"
    ).read_text()
    retro_operations_source = (
        FRONTEND_ROOT / "app" / "retro" / "operations" / "page.js"
    ).read_text()
    retro_approve_route = (
        FRONTEND_ROOT
        / "app"
        / "retro"
        / "operations"
        / "actions"
        / "proposals"
        / "[actionId]"
        / "approve"
        / "route.js"
    ).read_text()
    retro_dismiss_route = (
        FRONTEND_ROOT
        / "app"
        / "retro"
        / "operations"
        / "actions"
        / "proposals"
        / "[actionId]"
        / "dismiss"
        / "route.js"
    ).read_text()
    retro_schedule_dispatch_route = (
        FRONTEND_ROOT
        / "app"
        / "retro"
        / "control"
        / "execution"
        / "schedule-dispatches"
        / "route.js"
    ).read_text()
    retro_retry_route = (
        FRONTEND_ROOT
        / "app"
        / "retro"
        / "control"
        / "execution"
        / "dispatches"
        / "[dispatchId]"
        / "retry"
        / "route.js"
    ).read_text()
    retro_commands_route = (
        FRONTEND_ROOT / "app" / "retro" / "terminal" / "commands" / "route.js"
    ).read_text()
    retro_execute_route = (
        FRONTEND_ROOT / "app" / "retro" / "terminal" / "execute" / "route.js"
    ).read_text()
    retro_shell_source = (
        FRONTEND_ROOT / "components" / "retro-shell.js"
    ).read_text()
    retro_terminal_panel_source = (
        FRONTEND_ROOT / "components" / "retro-terminal-panel.js"
    ).read_text()
    control_terminal_source = (
        ROOT / "packages" / "application" / "use_cases" / "control_terminal.py"
    ).read_text()
    globals_source = (FRONTEND_ROOT / "app" / "globals.css").read_text()

    assert 'href="/retro"' in app_shell_source
    assert "{user ? (" in app_shell_source
    assert 'className="retroRoot"' in retro_layout_source
    assert "getWebRendererDiscovery()" in retro_page_source
    assert "optionalPanelData(getHouseholdOverview(), null)" in retro_page_source
    assert "optionalPanelData(getAttentionItems(), [])" in retro_page_source
    assert "optionalPanelData(getRecentChanges(), [])" in retro_page_source
    assert "MODULE_ORDER" in retro_page_source
    assert 'user.role === "admin"' in retro_page_source
    assert 'href: "/retro/money"' in retro_page_source
    assert 'href: "/retro/utilities"' in retro_page_source
    assert 'href: "/retro/operations"' in retro_page_source
    assert "/retro/operations#${descriptor.anchor}" in retro_page_source
    assert 'redirect("/retro")' in retro_control_source
    assert 'redirect("/retro")' in retro_catalog_source
    assert 'getExecutionSchedules({ includeArchived: true })' in retro_execution_source
    assert 'action="/retro/control/execution/schedule-dispatches"' in retro_execution_source
    assert "/retro/control/execution/dispatches/${record.dispatch_id}/retry" in retro_execution_source
    assert "getMonthlyCashflow()" in retro_money_source
    assert "getAffordabilityRatios()" in retro_money_source
    assert "id={descriptor.anchor}" in retro_money_source
    assert "getTerminalCommands()" in retro_terminal_source
    assert "RetroTerminalPanel" in retro_terminal_source
    assert "source systems, source assets, ingestion definitions, and publication definitions" in retro_terminal_source
    assert "getUtilityCostTrend(utilityType || undefined)" in retro_utilities_source
    assert "getContractReviewCandidates()" in retro_utilities_source
    assert 'descriptorByKey["utility-costs"]' in retro_utilities_source
    assert 'descriptorByKey["contract-review"]' in retro_utilities_source
    assert 'descriptorByKey["contract-renewals"]' in retro_utilities_source
    assert "id={descriptor.anchor}" in retro_utilities_source
    assert "getHaBridgeStatus()" in retro_operations_source
    assert "getHaEntities()" in retro_operations_source
    assert "getHaActionProposals()" in retro_operations_source
    assert "Approval Queue" in retro_operations_source
    assert "Approve" in retro_operations_source
    assert "Dismiss" in retro_operations_source
    assert 'const canManageApprovals = user.role === "admin";' in retro_operations_source
    assert "approval-approved" in retro_operations_source
    assert "approval-dismissed" in retro_operations_source
    assert "/api/ha/actions/proposals/{action_id}/approve" in retro_approve_route
    assert "/api/ha/actions/proposals/{action_id}/dismiss" in retro_dismiss_route
    assert "id={descriptor.anchor}" in retro_operations_source
    dispatch_route_helper = (FRONTEND_ROOT / "lib" / "execution-dispatch-routes.js").read_text()
    assert 'backendRequest("post", "/control/schedule-dispatches"' in dispatch_route_helper
    assert '"/control/schedule-dispatches/{dispatch_id}/retry"' in dispatch_route_helper
    assert "createScheduleDispatchHandler" in retro_schedule_dispatch_route
    assert 'basePath: "/retro/control/execution"' in retro_schedule_dispatch_route
    assert "createScheduleDispatchRetryHandler" in retro_retry_route
    assert "/retro/control/execution?notice=schedule-dispatch-retried" in retro_retry_route
    assert 'backendJsonRequest(\n    "get",\n    "/control/terminal/commands"' in retro_commands_route
    assert 'backendJsonRequest(\n    "post",\n    "/control/terminal/execute"' in retro_execute_route
    assert 'href: "/retro/money"' in retro_shell_source
    assert 'href: "/retro/utilities"' in retro_shell_source
    assert 'href: "/retro/operations"' in retro_shell_source
    assert 'href: "/retro/terminal"' in retro_shell_source
    assert 'fetch("/retro/terminal/execute"' in retro_terminal_panel_source
    assert "SYNC / NO SHELL ACCESS" in retro_terminal_panel_source
    assert 'usage="schedules [limit]"' in control_terminal_source
    assert 'usage="tokens [limit]"' in control_terminal_source
    assert 'usage="audit [limit]"' in control_terminal_source
    assert 'usage="publication-audit [limit]"' in control_terminal_source
    assert 'usage="users [limit]"' in control_terminal_source
    assert 'usage="source-systems [limit]"' in control_terminal_source
    assert 'usage="source-assets [limit]"' in control_terminal_source
    assert 'usage="ingestion-definitions [limit]"' in control_terminal_source
    assert 'usage="publication-definitions [limit]"' in control_terminal_source
    assert 'usage="lineage [limit]"' in control_terminal_source
    assert "--retro-bg" in globals_source


def test_nextjs_frontend_exposes_policy_authoring_surface() -> None:
    policies_page = (
        FRONTEND_ROOT / "app" / "control" / "policies" / "page.js"
    ).read_text()
    rule_summary = (
        FRONTEND_ROOT / "components" / "policy-rule-summary.js"
    ).read_text()
    control_nav = (FRONTEND_ROOT / "components" / "control-nav.js").read_text()
    backend_source = (FRONTEND_ROOT / "lib" / "backend.ts").read_text()

    # Admin-only, like every other control surface.
    assert "getCurrentUser()" in policies_page
    assert 'user.role !== "admin"' in policies_page
    assert 'redirect("/")' in policies_page

    # Data comes through the typed backend helpers, never raw transport.
    assert "getPolicyDefinitions()" in policies_page
    assert "getHaPolicyEvaluation()" in policies_page
    assert "getPolicyDefinitions" in backend_source
    assert "getReferenceablePublications" in backend_source
    assert '"/control/policies": "list_policies_control_policies_get"' in backend_source

    # The three distinctions A2 requires on the list.
    assert "source_kind" in policies_page
    assert "builtin" in policies_page
    assert "enabled" in policies_page

    # A verdict is shown with its reason, not on its own.
    assert "result.verdict" in policies_page
    assert "result.reason" in policies_page

    # Authority mode is visible, and a degraded mode says edits will not land.
    assert "authority" in policies_page
    assert "snapshot" in policies_page
    assert "will not take effect" in policies_page

    # Template discipline: the rule summary names the field, comparison and
    # publication actually evaluated rather than a friendly label.
    assert "publication_value_comparison" in rule_summary
    assert "publication_freshness_comparison" in rule_summary
    assert "ha_helper_state_comparison" in rule_summary
    assert "Reads publication" in rule_summary

    # Retired operators must not be offered by the authoring surface: they
    # validated but never fired, so a form control for them would do nothing.
    operator_phrases = rule_summary.split("COMPARISON_PHRASES = {", 1)[1].split("}", 1)[0]
    assert "not_in" not in operator_phrases
    assert "  in:" not in operator_phrases
    assert "gt:" in operator_phrases
    assert "neq:" in operator_phrases

    assert '{ href: "/control/policies", label: "Policies" }' in control_nav


def test_nextjs_frontend_policy_mutation_routes_follow_the_bff_pattern() -> None:
    policies_root = FRONTEND_ROOT / "app" / "control" / "policies"
    create_route = (policies_root / "create" / "route.js").read_text()
    update_route = (policies_root / "[policyId]" / "route.js").read_text()
    enabled_route = (policies_root / "[policyId]" / "enabled" / "route.js").read_text()
    delete_route = (policies_root / "[policyId]" / "delete" / "route.js").read_text()
    rule_form = (FRONTEND_ROOT / "lib" / "policy-rule-form.js").read_text()
    policy_form = (FRONTEND_ROOT / "components" / "policy-form.js").read_text()

    for source in (create_route, update_route, enabled_route, delete_route):
        assert "// @ts-check" in source
        assert "cookieHeader" in source

    assert 'backendRequest("post", "/control/policies"' in create_route
    assert 'backendRequest("patch", "/control/policies/{policy_id}"' in update_route
    assert 'backendRequest("patch", "/control/policies/{policy_id}"' in enabled_route
    assert 'backendRequest("delete", "/control/policies/{policy_id}"' in delete_route

    # Enable and disable are distinguishable, because enable re-validates the
    # stored publication references and can fail where disable cannot.
    assert "enable-failed" in enabled_route
    assert "disable-failed" in enabled_route

    # Only the chosen rule kind's fields are sent: every rule model forbids
    # extra keys, so carrying a field across from another kind is a 422.
    assert "publication_value_comparison" in rule_form
    assert "publication_freshness_comparison" in rule_form
    assert "ha_helper_state_comparison" in rule_form

    # Template discipline: required inputs are named and the submit is refused
    # until they are supplied, rather than failing on save.
    assert "requiredInputsMissing" in policy_form
    assert "disabled={missing.length > 0}" in policy_form
    assert "(required)" in policy_form
    # The form shows the field, comparison and threshold being evaluated.
    assert "This policy will evaluate" in policy_form
    # Only numerically comparable fields are offered.
    assert "column.comparable" in policy_form


def test_nextjs_frontend_policy_templates_are_parameterized_not_misleading() -> None:
    templates = (FRONTEND_ROOT / "lib" / "policy-templates.js").read_text()
    panel = (FRONTEND_ROOT / "components" / "policy-authoring-panel.js").read_text()

    # Each template names the publication and field it actually reads.
    assert "household_overview" in templates
    assert "cashflow_net" in templates
    assert "utility_cost_total" in templates
    assert "requiredInputs" in templates

    # A template that cannot decide a value for the operator leaves it empty
    # rather than inventing a default.
    assert '"threshold"' in templates
    assert '"publication_key"' in templates
    assert '"threshold_hours"' in templates

    # Rejected candidates are recorded with their reason rather than dropped
    # silently, including the multi-row read that makes a direct
    # monthly_cashflow rule dishonest.
    assert "TEMPLATE_EXCLUSIONS" in templates
    assert "monthly_cashflow" in templates
    assert "arbitrary month" in templates
    assert "subscription" in templates

    # The panel tells the operator what is still outstanding and why it
    # blocks enablement.
    assert "You must supply" in panel
    assert "cannot be created or enabled" in panel
    assert "Templates deliberately not offered" in panel


def test_nextjs_frontend_policy_preview_evaluates_the_document_it_would_save() -> None:
    preview_route = (
        FRONTEND_ROOT / "app" / "control" / "policies" / "preview" / "route.js"
    ).read_text()
    policy_form = (FRONTEND_ROOT / "components" / "policy-form.js").read_text()

    assert "// @ts-check" in preview_route
    assert 'backendJsonRequest(' in preview_route
    assert '"/control/policies/preview"' in preview_route
    # Status is passed through so the form can tell a rejected rule from an
    # evaluator that is not wired.
    assert "status: response.status" in preview_route

    # The preview button is gated on the same required inputs as save, and the
    # result is labelled as unsaved.
    assert "runPreview" in policy_form
    assert "disabled={missing.length > 0 || isPreviewing}" in policy_form
    assert "nothing has been saved" in policy_form
    # Verdict and reason are both shown, as on the list.
    assert "preview.verdict" in policy_form
    assert "preview.reason" in policy_form
    # The previewed document is built by the same helper the save path uses,
    # so a preview cannot drift from the rule that would be written.
    assert "buildRuleDocument" in policy_form


def test_nextjs_frontend_retro_policy_view_mirrors_verdicts_without_authoring() -> None:
    retro_policies = (
        FRONTEND_ROOT / "app" / "retro" / "control" / "policies" / "page.js"
    ).read_text()
    retro_shell = (FRONTEND_ROOT / "components" / "retro-shell.js").read_text()

    assert 'user.role !== "admin"' in retro_policies
    assert 'redirect("/retro")' in retro_policies
    assert "getPolicyDefinitions()" in retro_policies
    assert "getHaPolicyEvaluation()" in retro_policies

    # Verdict and reason are mirrored, as is the authority mode.
    assert "result.verdict" in retro_policies
    assert "result.reason" in retro_policies
    assert "Degraded authority" in retro_policies

    # Read-only by design: the retro shell mirrors what the classic surfaces
    # show rather than duplicating how they are edited.
    assert "<form" not in retro_policies
    assert "/control/policies" in retro_policies

    assert '{ href: "/retro/control/policies"' in retro_shell


def test_retro_shell_mirrors_control_agents_read_only() -> None:
    retro_agents = (
        FRONTEND_ROOT / "app" / "retro" / "control" / "agents" / "page.js"
    ).read_text()
    retro_shell = (FRONTEND_ROOT / "components" / "retro-shell.js").read_text()

    # Same audience as /control/agents: operators and admins.
    assert 'user.role !== "admin" && user.role !== "operator"' in retro_agents
    assert 'redirect("/retro")' in retro_agents
    # Reads the same typed helpers as the classic page; no direct fetches.
    for helper in ("getActionProposals()", "getAgentPrincipals()", "getAgentToolCatalog()"):
        assert helper in retro_agents
    assert "fetch(" not in retro_agents
    # Read-only mirror: no resolution forms or routes, resolution links to classic.
    assert "<form" not in retro_agents
    assert "/approve" not in retro_agents and "/dismiss" not in retro_agents
    assert 'href="/control/agents"' in retro_agents
    assert "resolution_reason" in retro_agents
    assert "actor_auth_provider" in retro_agents
    # Navigable for admins and operators.
    assert retro_shell.count('{ href: "/retro/control/agents"') == 2


def test_nextjs_frontend_exposes_deterministic_morning_brief() -> None:
    briefing_page = (FRONTEND_ROOT / "app" / "briefing" / "page.js").read_text()
    briefing_view = (FRONTEND_ROOT / "components" / "briefing-view.js").read_text()
    # The page fetches; BriefingView (shared with Storybook) renders.
    assert "<BriefingView brief={brief} renderExplain={renderExplain} surfaces={surfacesFor(user)} />" in briefing_page
    # Reader role does not get the operator-only source-freshness link.
    assert "surface.operatorOnly && user?.role === \"reader\"" in briefing_page
    assert "brief-surface-${section.key}" in briefing_view
    assert "@/lib/backend" not in briefing_view
    briefing_source = briefing_page + briefing_view
    lineage_source = (FRONTEND_ROOT / "app" / "briefing" / "lineage" / "page.js").read_text()
    backend_source = (FRONTEND_ROOT / "lib" / "backend.ts").read_text()

    # Server component reading through the typed backend helper only.
    assert "'use client'" not in briefing_source
    assert '"use client"' not in briefing_source
    assert "getBriefing" in briefing_source
    assert "getCurrentUser" in briefing_source
    assert "fetch(" not in briefing_source
    assert '"/api/briefing": "get_briefing_api_briefing_get"' in backend_source
    assert 'backendGet("/api/briefing")' in backend_source

    # Wave-1 primitives, not ad-hoc chips.
    for primitive in ('"./pill"', '"./num-mono"', '"./eyebrow"'):
        assert primitive in briefing_view

    # Every line shows claim status + confidence and links to the lineage drill.
    assert "item.claim_status" in briefing_source
    assert "ConfidenceLine" in briefing_source
    assert "item.remediation" in briefing_source
    assert "Next step:" in briefing_source
    assert "/briefing/lineage?publication_key=" in briefing_source
    assert "item.lineage_publication_key" in briefing_source
    assert "/runs/" in briefing_source
    assert "No language model" in briefing_source

    # The drill is server-rendered down to source runs.
    assert "'use client'" not in lineage_source
    assert '"use client"' not in lineage_source
    assert "getPublicationLineage" in lineage_source
    assert "fetch(" not in lineage_source
    assert "/runs/${encodeURIComponent(runId)}" in lineage_source
    assert '"source"' in lineage_source
    assert (
        '"/api/lineage/publication/{publication_key}": '
        '"get_publication_lineage_api_lineage_publication__publication_key__get"'
    ) in backend_source


def test_nextjs_frontend_exposes_battery_plan_outcome_and_decision_ledger() -> None:
    utilities_root = FRONTEND_ROOT / "app" / "utilities"
    page_root = utilities_root / "battery-plan"
    page = (page_root / "page.js").read_text()
    ledger_ui = (utilities_root / "_decisions" / "decision-ledger.js").read_text()
    handlers = (utilities_root / "_decisions" / "handlers.js").read_text()
    backend = (FRONTEND_ROOT / "lib" / "backend.ts").read_text()
    utilities_page = (utilities_root / "page.js").read_text()

    # Reads only through the typed reporting/control helpers.
    assert "getCurrentUser()" in page
    assert "getBatteryPlanOutcome(" in page
    assert "getDecisionRecords(DECISION_KEY)" in page
    assert "getDecisionReviews(DECISION_KEY)" in page
    assert "ReportingService(" not in page
    for helper in (
        "getBatteryPlanOutcome(",
        "getDecisionRecords(",
        "getDecisionSubjects(",
        "getDecisionReviews(",
    ):
        assert f"export async function {helper}" in backend
    assert (
        '"/reports/battery-plan-outcome": '
        '"get_battery_plan_outcome_reports_battery_plan_outcome_get";'
    ) in backend
    assert '"/control/decisions": "list_decisions_control_decisions_get";' in backend
    assert 'href="/utilities/battery-plan"' in utilities_page
    assert 'href="/utilities/energy-contract"' in utilities_page

    # Disclosures: verdict, remediation, per-value status, missing values,
    # tariff assumptions and lineage are rendered; estimates are not cash.
    for marker in (
        "insufficient_evidence",
        "row.remediation",
        "value.value_status",
        "value.is_missing",
        "tariff_snapshot_id",
        "source_run_ids_json",
        "not realized cash",
    ):
        assert marker in page

    # Only operators/admins see the decision forms; readers see history.
    assert 'user.role === "operator" || user.role === "admin"' in page
    assert "evidence_gaps_acknowledged" in ledger_ui
    assert "Recording a decision authorizes nothing" in ledger_ui
    # Commitment lifecycle and superseded evidence are rendered (HLA-K01/K02).
    for marker in (
        "decision.purpose",
        "stop_conditions",
        "review_triggers",
        "lifecycle.state",
        "superseded_by",
        "Evidence superseded",
        "record.history",
    ):
        assert marker in ledger_ui

    # Route handlers delegate to the shared, cookie-forwarding handlers.
    assert "// @ts-check" in handlers
    assert "cookieHeader" in handlers
    assert 'backendRequest("post", "/control/decisions"' in handlers
    assert '"/control/decisions/{decision_id}/follow-ups"' in handlers
    assert '"/control/decisions/{decision_id}/stop"' in handlers
    assert '"/control/decisions/{decision_id}/reopen"' in handlers
    assert '"/control/decisions/evidence-trace"' in handlers
    assert "toISOString()" in handlers
    for page_dir in ("battery-plan", "energy-contract"):
        for route in (
            "decisions/route.js",
            "decisions/[decisionId]/follow-ups/route.js",
            "decisions/[decisionId]/stop/route.js",
            "decisions/[decisionId]/reopen/route.js",
            "evidence-trace/route.js",
        ):
            source = (utilities_root / page_dir / route).read_text()
            assert "// @ts-check" in source
            assert "_decisions/handlers" in source
            assert f'"/utilities/{page_dir}"' in source


def test_nextjs_frontend_exposes_energy_contract_decision_page() -> None:
    page = (FRONTEND_ROOT / "app" / "utilities" / "energy-contract" / "page.js").read_text()
    assert 'const DECISION_KEY = "electricity_contract_keep_or_switch";' in page
    assert "getDecisionSubjects(DECISION_KEY" in page
    assert "getDecisionRecords(DECISION_KEY)" in page
    assert "ReportingService(" not in page
    assert 'user.role === "operator" || user.role === "admin"' in page
    for marker in (
        "insufficient_evidence",
        "assessment.remediation",
        "assessment.limitations",
        "value_disclosures",
        "not realized cash",
        "Nothing here can switch or cancel a contract",
    ):
        assert marker in page


def test_nextjs_frontend_exposes_agent_control_surface() -> None:
    agents_root = FRONTEND_ROOT / "app" / "control" / "agents"
    page = (agents_root / "page.js").read_text()
    approve_route = (agents_root / "proposals" / "[actionId]" / "approve" / "route.js").read_text()
    dismiss_route = (agents_root / "proposals" / "[actionId]" / "dismiss" / "route.js").read_text()
    resolution = (FRONTEND_ROOT / "lib" / "agent-proposal-resolution.js").read_text()
    control_nav = (FRONTEND_ROOT / "components" / "control-nav.js").read_text()
    backend = (FRONTEND_ROOT / "lib" / "backend.ts").read_text()

    # Admin-only, server-fetched through the shared backend helper (ADR 4.3).
    assert 'user.role !== "admin"' in page
    assert "'use client'" not in page and '"use client"' not in page
    for helper in (
        "getActionProposals(",
        "getActionProposalReview(",
        "getAgentPrincipals(",
        "getAgentToolCatalog(",
    ):
        assert helper in page
    assert 'backendGet("/api/actions/proposals/{action_id}/review"' in backend
    assert 'backendGet("/api/agent/catalog")' in backend

    # A nav entry exists, so the page is reachable (ADR section 5).
    assert '{ href: "/control/agents", label: "Agents" }' in control_nav

    # The inbox shows what approval does, the diff, evidence, and caveats.
    for marker in ("What approval does.", "ChangePreview", "EvidenceList", "trust.caveats"):
        assert marker in page
    # Lineage drill-down from each cited publication.
    assert "/control/lineage?publication_key=" in page
    # Approve and reject share one reason field.
    assert 'name="reason"' in page
    assert "formAction=" in page

    # Mutations follow the BFF pattern with typed literal paths.
    for source in (approve_route, dismiss_route):
        assert "// @ts-check" in source
        assert "cookieHeader" in source
        assert "resolutionReason(request)" in source
    assert 'backendRequest(\n    "post",\n    "/api/actions/proposals/{action_id}/approve"' in approve_route
    assert 'backendRequest(\n    "post",\n    "/api/actions/proposals/{action_id}/dismiss"' in dismiss_route

    # Conflict and machine-principal refusals get their own notices.
    assert "proposal-already-resolved" in resolution
    assert "proposal-forbidden" in resolution
    assert "proposal-already-resolved" in page
    assert "proposal-forbidden" in page


def _nav_model_hrefs(source: str) -> set[str]:
    import re

    return set(re.findall(r'href: "([^"]+)"', source))


def test_default_shell_nav_registry_covers_every_top_level_route() -> None:
    nav_model = (FRONTEND_ROOT / "lib" / "nav-model.js").read_text()
    app_shell = (FRONTEND_ROOT / "components" / "app-shell.js").read_text()
    palette = (FRONTEND_ROOT / "components" / "command-palette.js").read_text()

    # One registry, rendered by the rail and the palette (ADR web-surface-shell-decision §4.2).
    assert "navGroupsForUser" in app_shell
    assert "paletteEntriesForUser" in app_shell
    assert "function navItemsForUser" not in app_shell
    assert "filterPaletteEntries" in palette
    assert 'aria-label="Primary"' in app_shell
    assert 'href="#main-content"' in app_shell

    hrefs = _nav_model_hrefs(nav_model)
    unlisted_block = nav_model.split("NAV_UNLISTED_ROUTES = {", 1)[1].split("};", 1)[0]
    unlisted = {
        line.split(":", 1)[0].strip().strip('"')
        for line in unlisted_block.splitlines()
        if ":" in line
    }
    missing = []
    for child in sorted((FRONTEND_ROOT / "app").iterdir()):
        if not child.is_dir():
            continue
        if f"/{child.name}" in hrefs or child.name in unlisted:
            continue
        missing.append(child.name)
    assert missing == [], f"top-level routes without a nav entry: {missing}"
    # Role visibility lives in the registry.
    assert '{ href: "/control", label: "Control", group: "admin", minRole: "admin"' in nav_model
    assert 'href: "/upload", label: "Upload", group: "data", minRole: "operator"' in nav_model


def test_cashflow_map_page_reads_reporting_api_and_discloses_provenance() -> None:
    page = (FRONTEND_ROOT / "app" / "cashflow" / "page.js").read_text()
    sankey = (FRONTEND_ROOT / "components" / "cashflow-sankey.js").read_text()
    backend = (FRONTEND_ROOT / "lib" / "backend.ts").read_text()

    assert '"/reports/cashflow-map": "get_cashflow_map_reports_cashflow_map_get"' in backend
    assert "export async function getCashflowMap" in backend
    assert "getCashflowMap({ month: requestedMonth, includeTransfers })" in page
    # Month and drill-down state live in the URL, not component state.
    assert "searchParams?.m" in page
    assert "searchParams?.focus" in page
    assert "useState" not in page
    assert '"use client"' not in page
    # Honest disclosure: staleness, transfers, provenance and lineage.
    assert 'tone="stale"' in page
    assert "payload.provenance" in page
    # Lineage and confidence per publication come from the shared <Explain> loader.
    assert "loadExplanation(key, { user })" in page
    assert "ExplainBox" in page
    assert "AsOfScrubber" in page
    assert "Show transfers between own accounts" in page
    # Confidence is an admin read; other roles must not trigger it (lib/explain.js).
    explain_loader = (FRONTEND_ROOT / "lib" / "explain.js").read_text()
    assert "confidence === undefined && isAdmin ? confidenceIndex() : Promise.resolve(null)" in explain_loader
    # No chart library; readable alternative for narrow screens.
    assert "d3" not in sankey
    assert "export function CashflowFlowList" in sankey
    assert "fetch(" not in page


def test_wallboard_page_is_ambient_and_degrades_per_tile() -> None:
    page = (FRONTEND_ROOT / "app" / "wallboard" / "page.js").read_text()
    live = (FRONTEND_ROOT / "components" / "wallboard-live.js").read_text()
    view = (FRONTEND_ROOT / "components" / "wallboard-view.js").read_text()
    css = (FRONTEND_ROOT / "app" / "wallboard.css").read_text()

    panels = (FRONTEND_ROOT / "components" / "wallboard-panels.js").read_text()

    assert "await getCurrentUser()" in page
    assert 'searchParams?.compact === "1"' in page
    # Adapters are optional: a missing one renders that panel's own state.
    for adapter in ("getServiceHealth()", "getDeviceReadings()", "getPowerSeries(24)", "getHaBridgeStatus()"):
        assert f"optional({adapter}, null)" in page
    assert "compact ? null : optional(getEventFeed(), null)" in page
    assert "AppShell" not in page
    # Compact is URL-only.
    for source in (page, live, view):
        assert "localStorage" not in source
    # 30s refresh; pauses while the page is hidden and refreshes on return;
    # freezes on hover; no streaming. Not gated on focus: kiosk browsers
    # rarely get it, and hasFocus gating starves the display.
    assert "REFRESH_MS = 30_000" in live
    assert "router.refresh()" in live
    assert 'document.visibilityState === "hidden"' in live
    assert 'addEventListener("visibilitychange", onVisibility)' in live
    assert "if (wasHidden && !hidden && !pauseReason(stateRef.current)) refreshRef.current();" in live
    assert "hasFocus()" not in live
    assert "pointerenter" in live
    assert 'key === "r"' in live and 'key === "p"' in live
    assert "No services reporting" in panels
    assert "Not connected" in panels
    # Kiosk grid.
    assert '"services events"' in css
    assert '"devices power"' in css
    assert '"ticker ticker"' in css
    assert "minmax(0, 1.4fr) minmax(0, 1fr)" in css
    # Mono only and readable from a distance; status 24px+.
    assert "var(--retro-font-mono)" in css
    assert "--font-display" not in css
    assert "serif" not in css.replace("monospace", "")
    import re

    fixed_sizes = [int(size) for size in re.findall(r"font-size: (\d+)px", css)]
    assert fixed_sizes and min(fixed_sizes) >= 18
    status_block = css.split(".wallStatus {", 1)[1].split("}", 1)[0]
    assert "font-size: 24px" in status_block
    # Cursor blink is the only animation, and it honours reduced motion.
    assert css.count("@keyframes") == 1
    assert "transition" not in css
    assert "@media (prefers-reduced-motion: reduce)" in css


def test_wallboard_scanlines_match_retro_root() -> None:
    css = (FRONTEND_ROOT / "app" / "wallboard.css").read_text()
    globals_css = (FRONTEND_ROOT / "app" / "globals.css").read_text()

    def block(source: str, selector: str) -> str:
        return source.split(f"{selector} {{", 1)[1].split("\n}", 1)[0].strip()

    assert block(css, "body:has(.wall)::before") == block(globals_css, ".retroRoot::before")
    assert block(css, "body:has(.wall)::after") == block(globals_css, ".retroRoot::after")


def test_control_lineage_page_reads_through_the_backend_helper() -> None:
    page = (FRONTEND_ROOT / "app" / "control" / "lineage" / "page.js").read_text()
    control_nav = (FRONTEND_ROOT / "components" / "control-nav.js").read_text()

    # Server component over lib/backend.ts (ADR §4.3); no browser-relative fetches
    # that split-origin deployments cannot route to the API.
    assert "use client" not in page
    assert "fetch(" not in page
    assert "useEffect" not in page
    assert "await getCurrentUser()" in page
    assert "await getPublicationLineage(publicationKey)" in page
    assert "searchParams?.publication_key" in page
    assert 'tone="error"' in page
    assert "No lineage recorded yet" in page
    assert '{ href: "/control/lineage", label: "Lineage" }' in control_nav


def test_default_shell_has_route_level_error_loading_and_not_found_states() -> None:
    error_page = (FRONTEND_ROOT / "app" / "error.js").read_text()
    not_found = (FRONTEND_ROOT / "app" / "not-found.js").read_text()
    loading = (FRONTEND_ROOT / "app" / "loading.js").read_text()
    state_panel = (FRONTEND_ROOT / "components" / "state-panel.js").read_text()
    dashboard = (FRONTEND_ROOT / "app" / "page.js").read_text()

    assert error_page.startswith('"use client"')
    assert "reset()" in error_page
    assert "Backend request failed for" in error_page
    assert "StatePanel" in not_found
    assert 'aria-busy="true"' in loading
    for tone in ("empty", "stale", "error", "loading"):
        assert tone in state_panel
    # The dashboard no longer fails for non-admin roles on the admin-only freshness read.
    assert 'user?.role === "admin" ? getSourceFreshness() : Promise.resolve([])' in dashboard


def test_control_confidence_page_is_a_server_component() -> None:
    page = (FRONTEND_ROOT / "app" / "control" / "confidence" / "page.js").read_text()
    backend = (FRONTEND_ROOT / "lib" / "backend.ts").read_text()

    # ADR web-surface-shell-decision §4.3: no browser-relative fetches that
    # split-origin deployments cannot route to the API.
    assert "use client" not in page
    assert "fetch(" not in page
    assert "useEffect" not in page
    assert "useState" not in page
    assert "await getCurrentUser()" in page
    assert "await getPublicationConfidence({ staleOnly" in page
    # Filters live in the URL.
    assert 'searchParams?.stale === "1"' in page
    assert "searchParams?.verdict" in page
    assert 'action="/control/confidence" method="get"' in page
    assert 'tone="error"' in page
    assert "ResponsiveTable" in page
    assert "data-testid={`lineage-link-${pub.publication_key}`}" in page
    assert "verdict?: QueryValue<\"/control/confidence\", \"verdict\">" in backend


def test_sources_page_joins_runs_per_source_asset() -> None:
    page = (FRONTEND_ROOT / "app" / "sources" / "page.js").read_text()

    # Regression: rows were keyed and joined by dataset, so every asset of one
    # dataset showed the same source. Join on the asset's own latest run.
    assert "lastRunByDataset" not in page
    assert "runsById.get(ds.latest_run_id)" in page
    assert "row.source_asset_id || row.dataset_name" in page
    assert "ResponsiveTable" in page
    # Status colours use tokens that exist.
    assert "var(--error)" not in page
    assert "var(--warning)" not in page


def test_explain_primitive_is_server_loaded_and_accessible() -> None:
    explain = (FRONTEND_ROOT / "components" / "explain.js").read_text()
    disclosure = (FRONTEND_ROOT / "components" / "explain-disclosure.js").read_text()
    server = (FRONTEND_ROOT / "components" / "explain-server.js").read_text()
    loader = (FRONTEND_ROOT / "lib" / "explain.js").read_text()
    css = (FRONTEND_ROOT / "app" / "primitives.css").read_text()

    # Data comes through lib/backend.ts on the server, deduplicated per request.
    assert "use client" not in loader
    assert 'import { cache } from "react"' in loader
    assert "getPublicationLineage(publicationKey)" in loader
    assert "fetch(" not in loader + explain + disclosure
    assert "loadExplanation(publication" in server
    # Native disclosure: keyboard operable without script; Escape returns focus.
    assert disclosure.startswith('"use client"')
    assert "<details" in disclosure and "<summary" in disclosure
    assert 'event.key === "Escape"' in disclosure
    assert "summary?.focus()" in disclosure
    assert 'className="srOnly"' in disclosure
    # Honest when lineage is a single node.
    assert "No runs or sources recorded behind it yet" in explain
    assert "/briefing/lineage?publication_key=" in explain
    # Stays on screen at phone width.
    assert "@media (max-width: 600px)" in css

    adopters = {
        "app/page.js": "<Explain",
        "app/cashflow/page.js": "<ExplainBox",
        "app/briefing/page.js": "<Explain",
        "components/wallboard-view.js": "<ExplainBox",
    }
    for path, marker in adopters.items():
        assert marker in (FRONTEND_ROOT / path).read_text(), path
    # Briefing adoption is presentation only: it reuses the brief's confidence.
    assert "confidence={item.confidence || null}" in (FRONTEND_ROOT / "app" / "briefing" / "page.js").read_text()


def test_as_of_scrubber_only_offers_published_months() -> None:
    scrubber = (FRONTEND_ROOT / "components" / "as-of-scrubber.js").read_text()
    dashboard = (FRONTEND_ROOT / "app" / "page.js").read_text()

    assert "use client" not in scrubber
    assert 'aria-current={month === selected ? "true" : undefined}' in scrubber
    assert "no published data" in scrubber
    # The dashboard rewinds month-keyed publications by month and reads the
    # current-only publications from their dated snapshots; state is in the URL.
    assert "searchParams?.asof" in dashboard
    assert "publishedMonths.includes(requestedAsOf)" in dashboard
    assert "visibleCashflow" in dashboard
    assert '"mart_monthly_cashflow"' in dashboard
    # Nothing is marked "Today" any more: every current-only panel has history.
    assert ">Today</span>" not in dashboard


def test_dashboard_reads_current_only_panels_from_snapshots() -> None:
    dashboard = (FRONTEND_ROOT / "app" / "page.js").read_text()
    history = (FRONTEND_ROOT / "components" / "as-of-history.js").read_text()
    backend = (FRONTEND_ROOT / "lib" / "backend.ts").read_text()

    for helper in (
        "getHouseholdOverviewAsOf",
        "getAttentionItemsAsOf",
        "getRecentChangesAsOf",
        "getSubscriptionSummaryAsOf",
        "getAffordabilityRatiosAsOf",
        "getRecurringCostBaselineAsOf",
    ):
        assert f"{helper}(month)" in dashboard
        assert f"export async function {helper}(asOf: string)" in backend
    assert "params: { query: { as_of: asOf } }" in backend
    # Honest gaps: a month without a snapshot shows "No history", not today.
    for read in ("ratios", "baseline", "subscriptions", "attention", "changes"):
        assert f"noHistory(reads.{read})" in dashboard
        assert f"<HistoryTag read={{reads.{read}}} />" in dashboard
    assert 'read.status === "no_history"' in dashboard
    assert "No history for ${formatMonth(month)}" in history
    assert "As published ${day}" in history


def test_responsive_table_keeps_table_semantics_at_phone_width() -> None:
    table = (FRONTEND_ROOT / "components" / "responsive-table.js").read_text()
    css = (FRONTEND_ROOT / "app" / "primitives.css").read_text()

    assert "use client" not in table
    assert "<table>" in table and "<thead>" in table and 'scope="col"' in table
    assert "data-label=" in table
    assert 'role="region"' in table and "tabIndex={0}" in table
    assert "content: attr(data-label);" in css
    for path in ("app/page.js", "app/sources/page.js", "app/control/confidence/page.js"):
        assert "<ResponsiveTable" in (FRONTEND_ROOT / path).read_text(), path
