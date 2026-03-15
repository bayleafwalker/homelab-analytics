from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = ROOT / "apps" / "web" / "frontend"


def test_nextjs_frontend_exposes_login_and_logout_routes() -> None:
    login_route = (FRONTEND_ROOT / "app" / "auth" / "login" / "route.js").read_text()
    logout_route = (FRONTEND_ROOT / "app" / "auth" / "logout" / "route.js").read_text()
    login_page = (FRONTEND_ROOT / "app" / "login" / "page.js").read_text()
    control_page = (FRONTEND_ROOT / "app" / "control" / "page.js").read_text()
    control_catalog_page = (
        FRONTEND_ROOT / "app" / "control" / "catalog" / "page.js"
    ).read_text()
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
    run_detail_page = (
        FRONTEND_ROOT / "app" / "runs" / "[runId]" / "page.js"
    ).read_text()
    run_retry_route = (
        FRONTEND_ROOT / "app" / "runs" / "[runId]" / "retry" / "route.js"
    ).read_text()

    assert 'backendRequest("/auth/login"' in login_route
    assert "set-cookie" in login_route
    assert 'backendRequest("/auth/logout"' in logout_route
    assert "Sign In" in login_page
    assert 'action="/auth/login"' in login_page
    assert "Too many failed login attempts" in login_page
    assert "getLocalUsers" in control_page
    assert "getAuthAuditEvents" in control_page
    assert "getSourceSystems" in control_catalog_page
    assert "getSourceAssets" in control_catalog_page
    assert "getOperationalSummary" in control_catalog_page
    assert "getDatasetContractDiff" in control_catalog_page
    assert "getColumnMappingDiff" in control_catalog_page
    assert "MappingPreviewPanel" in control_catalog_page
    assert "Create dataset contract version" in control_catalog_page
    assert "Create column mapping version" in control_catalog_page
    assert "parseColumnsSpec" in dataset_contract_route
    assert "/config/dataset-contracts" in dataset_contract_route
    assert "/config/dataset-contracts/${params.datasetContractId}/archive" in dataset_contract_archive_route
    assert "parseRulesSpec" in column_mapping_route
    assert "/config/column-mappings" in column_mapping_route
    assert "/config/column-mappings/${params.columnMappingId}/archive" in column_mapping_archive_route
    assert 'backendRequest("/config/column-mappings/preview"' in preview_route
    assert "getIngestionDefinitions" in control_execution_page
    assert "getExecutionSchedules" in control_execution_page
    assert "getOperationalSummary" in control_execution_page
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
    assert 'backendRequest("/config/source-systems"' in source_system_route
    assert 'backendRequest(`/config/source-systems/${params.sourceSystemId}`' in source_system_update_route
    assert 'backendRequest("/config/source-assets"' in source_asset_route
    assert 'backendRequest(`/config/source-assets/${params.sourceAssetId}`' in source_asset_update_route
    assert "/config/source-assets/${params.sourceAssetId}/archive" in source_asset_archive_route
    assert "/config/source-assets/${params.sourceAssetId}" in source_asset_delete_route
    assert 'backendRequest("/config/ingestion-definitions"' in ingestion_definition_route
    assert "/config/ingestion-definitions/${params.ingestionDefinitionId}" in ingestion_definition_update_route
    assert "/config/ingestion-definitions/${params.ingestionDefinitionId}/archive" in ingestion_definition_archive_route
    assert "/config/ingestion-definitions/${params.ingestionDefinitionId}" in ingestion_definition_delete_route
    assert 'backendRequest("/config/execution-schedules"' in execution_schedule_route
    assert "/config/execution-schedules/${params.scheduleId}" in execution_schedule_update_route
    assert "/config/execution-schedules/${params.scheduleId}/archive" in execution_schedule_archive_route
    assert "/config/execution-schedules/${params.scheduleId}" in execution_schedule_delete_route
    assert 'backendRequest("/control/schedule-dispatches"' in schedule_dispatch_route
    assert "getScheduleDispatch" in dispatch_detail_page
    assert "getOperationalSummary" in dispatch_detail_page
    assert "/ingest/ingestion-definitions/${params.ingestionDefinitionId}/process" in process_definition_route
    assert 'backendRequest(`/runs/${params.runId}/retry`' in run_retry_route
    assert "Retry run" in run_detail_page


def test_nextjs_frontend_reads_data_from_api_helper_only() -> None:
    dashboard_source = (FRONTEND_ROOT / "app" / "page.js").read_text()
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
    backend_source = (FRONTEND_ROOT / "lib" / "backend.js").read_text()
    upload_route_helper = (FRONTEND_ROOT / "lib" / "upload-route.js").read_text()

    assert "HOMELAB_ANALYTICS_API_BASE_URL" in backend_source
    assert 'fetch(`${getApiBaseUrl()}${path}`' in backend_source
    assert 'outboundHeaders.set("x-csrf-token", csrfToken)' in backend_source
    assert "getSourceSystems" in backend_source
    assert "getSourceAssets" in backend_source
    assert "getDatasetContracts" in backend_source
    assert "getColumnMappings" in backend_source
    assert "getIngestionDefinitions" in backend_source
    assert "getExecutionSchedules" in backend_source
    assert "getOperationalSummary" in backend_source
    assert "getScheduleDispatch" in backend_source
    assert "getDatasetContractDiff" in backend_source
    assert "getColumnMappingDiff" in backend_source
    assert "getRunsPage" in backend_source
    assert "getRun" in backend_source
    assert "getTransformationAudit" in backend_source
    assert "getMonthlyCashflow" in dashboard_source
    assert "getRuns" in dashboard_source
    assert "getRunsPage" in runs_source
    assert "getMonthlyCashflow" in reports_source
    assert "getLocalUsers" in control_source
    assert "getSourceSystems" in control_catalog_source
    assert "getDatasetContracts({ includeArchived: true })" in control_catalog_source
    assert "getColumnMappings({ includeArchived: true })" in control_catalog_source
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
