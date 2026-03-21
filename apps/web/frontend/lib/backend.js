import { cookies } from "next/headers";
import { redirect } from "next/navigation";

const API_BASE_URL =
  process.env.HOMELAB_ANALYTICS_API_BASE_URL || "http://127.0.0.1:8080";
const CSRF_COOKIE_NAME = "homelab_analytics_csrf";

export function getApiBaseUrl() {
  return API_BASE_URL.replace(/\/$/, "");
}

function buildQuery(params = {}) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") {
      continue;
    }
    query.set(key, String(value));
  }
  const serialized = query.toString();
  return serialized ? `?${serialized}` : "";
}

function getCookieValue(cookieHeader, name) {
  return (cookieHeader || "")
    .split(";")
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => {
      const separator = part.indexOf("=");
      if (separator === -1) {
        return [part, ""];
      }
      return [part.slice(0, separator), part.slice(separator + 1)];
    })
    .find(([cookieName]) => cookieName === name)?.[1];
}

export async function backendRequest(
  path,
  {
    method = "GET",
    headers = {},
    body,
    cookieHeader,
    contentType
  } = {}
) {
  const outboundHeaders = new Headers(headers);
  const currentCookies = cookieHeader ?? cookies().toString();
  if (currentCookies) {
    outboundHeaders.set("cookie", currentCookies);
  }
  if (!["GET", "HEAD", "OPTIONS"].includes(method.toUpperCase())) {
    const csrfToken = getCookieValue(currentCookies, CSRF_COOKIE_NAME);
    if (csrfToken) {
      outboundHeaders.set("x-csrf-token", csrfToken);
    }
  }
  if (contentType && !outboundHeaders.has("content-type")) {
    outboundHeaders.set("content-type", contentType);
  }
  return fetch(`${getApiBaseUrl()}${path}`, {
    method,
    headers: outboundHeaders,
    body,
    cache: "no-store",
    redirect: "manual"
  });
}

export function copyBackendSetCookies(sourceResponse, targetHeaders) {
  const getSetCookie = sourceResponse.headers.getSetCookie?.bind(sourceResponse.headers);
  const cookieValues = getSetCookie
    ? getSetCookie()
    : [sourceResponse.headers.get("set-cookie")].filter(Boolean);
  for (const cookieValue of cookieValues) {
    targetHeaders.append("set-cookie", cookieValue);
  }
}

export async function backendJson(path) {
  const response = await backendRequest(path);
  if (response.status === 401) {
    redirect("/login");
  }
  if (!response.ok) {
    throw new Error(`Backend request failed for ${path}: ${response.status}`);
  }
  return response.json();
}

export async function getCurrentUser() {
  const payload = await backendJson("/auth/me");
  return payload.user;
}

export async function getRuns(limit = 8) {
  const payload = await backendJson(`/runs${buildQuery({ limit })}`);
  return payload.runs || [];
}

export async function getRunsPage({
  dataset,
  status,
  fromDate,
  toDate,
  limit = 50,
  offset = 0
} = {}) {
  return backendJson(
    `/runs${buildQuery({
      dataset,
      status,
      from_date: fromDate,
      to_date: toDate,
      limit,
      offset
    })}`
  );
}

export async function getRun(runId) {
  const payload = await backendJson(`/runs/${runId}`);
  return payload.run;
}

export async function getHouseholdOverview() {
  const payload = await backendJson("/reports/household-overview");
  return payload.rows?.[0] || null;
}
export async function getAttentionItems() {
  const payload = await backendJson("/reports/attention-items");
  return payload.rows || [];
}
export async function getRecentChanges() {
  const payload = await backendJson("/reports/recent-changes");
  return payload.rows || [];
}
export async function getSpendByCategoryMonthly() {
  const payload = await backendJson("/reports/spend-by-category-monthly");
  return payload.rows || [];
}
export async function getRecentLargeTransactions() {
  const payload = await backendJson("/reports/recent-large-transactions");
  return payload.rows || [];
}
export async function getAccountBalanceTrend() {
  const payload = await backendJson("/reports/account-balance-trend");
  return payload.rows || [];
}
export async function getTransactionAnomalies() {
  const payload = await backendJson("/reports/transaction-anomalies");
  return payload.rows || [];
}
export async function getUpcomingFixedCosts() {
  const payload = await backendJson("/reports/upcoming-fixed-costs");
  return payload.rows || [];
}
export async function getUtilityCostTrend(utilityType) {
  const payload = await backendJson(
    `/reports/utility-cost-trend${buildQuery({ utility_type: utilityType })}`
  );
  return payload.rows || [];
}

export async function getUtilityCostSummary(utilityType, meterId, fromPeriod, toPeriod) {
  const payload = await backendJson(
    `/reports/utility-cost-summary${buildQuery({
      utility_type: utilityType,
      meter_id: meterId,
      from_period: fromPeriod,
      to_period: toPeriod,
    })}`
  );
  return payload.rows || [];
}

export async function getUsageVsPrice(utilityType) {
  const payload = await backendJson(
    `/reports/usage-vs-price${buildQuery({ utility_type: utilityType })}`
  );
  return payload.rows || [];
}
export async function getContractReviewCandidates() {
  const payload = await backendJson("/reports/contract-review-candidates");
  return payload.rows || [];
}
export async function getContractRenewalWatchlist() {
  const payload = await backendJson("/reports/contract-renewal-watchlist");
  return payload.rows || [];
}
export async function getSubscriptionSummary() {
  const payload = await backendJson("/reports/subscription-summary");
  return payload.rows || [];
}
export async function getCategoryDimension() {
  const payload = await backendJson("/reports/current-dimensions/dim_category");
  return payload.rows || [];
}

export async function getMonthlyCashflow() {
  const payload = await backendJson("/reports/monthly-cashflow");
  return payload.rows || [];
}

export async function getSourceSystems() {
  const payload = await backendJson("/config/source-systems");
  return payload.source_systems || [];
}

export async function getDatasetContracts({ includeArchived = false } = {}) {
  const payload = await backendJson(
    `/config/dataset-contracts${buildQuery({ include_archived: includeArchived })}`
  );
  return payload.dataset_contracts || [];
}

export async function getDatasetContractDiff(leftId, rightId) {
  const payload = await backendJson(
    `/config/dataset-contracts/${leftId}/diff${buildQuery({ other_id: rightId })}`
  );
  return payload.diff;
}

export async function getColumnMappings({ includeArchived = false } = {}) {
  const payload = await backendJson(
    `/config/column-mappings${buildQuery({ include_archived: includeArchived })}`
  );
  return payload.column_mappings || [];
}

export async function getColumnMappingDiff(leftId, rightId) {
  const payload = await backendJson(
    `/config/column-mappings/${leftId}/diff${buildQuery({ other_id: rightId })}`
  );
  return payload.diff;
}

export async function getTransformationHandlers() {
  const payload = await backendJson("/config/transformation-handlers");
  return payload.transformation_handlers || [];
}

export async function getPublicationKeys() {
  const payload = await backendJson("/config/publication-keys");
  return payload.publication_keys || [];
}

export async function getExtensionRegistrySources({ includeArchived = false } = {}) {
  const payload = await backendJson(
    `/config/extension-registry-sources${buildQuery({
      include_archived: includeArchived
    })}`
  );
  return payload.extension_registry_sources || [];
}

export async function getExtensionRegistryRevisions({
  extensionRegistrySourceId
} = {}) {
  const payload = await backendJson(
    `/config/extension-registry-revisions${buildQuery({
      extension_registry_source_id: extensionRegistrySourceId
    })}`
  );
  return payload.extension_registry_revisions || [];
}

export async function getExtensionRegistryActivations() {
  const payload = await backendJson("/config/extension-registry-activations");
  return payload.extension_registry_activations || [];
}

export async function getFunctions() {
  const payload = await backendJson("/functions");
  return payload.functions || {};
}

export async function getHaEntities(entityClass = null) {
  const payload = await backendJson(`/api/ha/entities${buildQuery({ entity_class: entityClass })}`);
  return payload.rows || [];
}

export async function getHaEntityHistory(entityId, limit = 50) {
  const payload = await backendJson(`/api/ha/entities/${entityId}/history${buildQuery({ limit })}`);
  return payload.rows || [];
}

export async function getTransformationPackages({ includeArchived = false } = {}) {
  const payload = await backendJson(
    `/config/transformation-packages${buildQuery({
      include_archived: includeArchived
    })}`
  );
  return payload.transformation_packages || [];
}

export async function getPublicationDefinitions({
  transformationPackageId,
  includeArchived = false
} = {}) {
  const payload = await backendJson(
    `/config/publication-definitions${buildQuery({
      transformation_package_id: transformationPackageId,
      include_archived: includeArchived
    })}`
  );
  return payload.publication_definitions || [];
}

export async function getSourceAssets({ includeArchived = false } = {}) {
  const payload = await backendJson(
    `/config/source-assets${buildQuery({ include_archived: includeArchived })}`
  );
  return payload.source_assets || [];
}

export async function getIngestionDefinitions({ includeArchived = false } = {}) {
  const payload = await backendJson(
    `/config/ingestion-definitions${buildQuery({
      include_archived: includeArchived
    })}`
  );
  return payload.ingestion_definitions || [];
}

export async function getExecutionSchedules({ includeArchived = false } = {}) {
  const payload = await backendJson(
    `/config/execution-schedules${buildQuery({
      include_archived: includeArchived
    })}`
  );
  return payload.execution_schedules || [];
}

export async function getLocalUsers() {
  const payload = await backendJson("/auth/users");
  return payload.users || [];
}

export async function getServiceTokens({ includeRevoked = false } = {}) {
  const payload = await backendJson(
    `/auth/service-tokens${buildQuery({ include_revoked: includeRevoked })}`
  );
  return payload.service_tokens || [];
}

export async function getAuthAuditEvents(limit = 30) {
  const payload = await backendJson(`/control/auth-audit?limit=${limit}`);
  return payload.auth_audit_events || [];
}

export async function getSourceLineage({ runId, targetLayer } = {}) {
  const payload = await backendJson(
    `/control/source-lineage${buildQuery({ run_id: runId, target_layer: targetLayer })}`
  );
  return payload.lineage || [];
}

export async function getPublicationAudit({ runId, publicationKey } = {}) {
  const payload = await backendJson(
    `/control/publication-audit${buildQuery({
      run_id: runId,
      publication_key: publicationKey
    })}`
  );
  return payload.publication_audit || [];
}

export async function getScheduleDispatches({ scheduleId, status } = {}) {
  const payload = await backendJson(
    `/control/schedule-dispatches${buildQuery({
      schedule_id: scheduleId,
      status
    })}`
  );
  return payload.dispatches || [];
}

export async function getScheduleDispatch(dispatchId) {
  const payload = await backendJson(`/control/schedule-dispatches/${dispatchId}`);
  return payload;
}

export async function getOperationalSummary() {
  return backendJson("/control/operational-summary");
}

export async function getSourceFreshness() {
  const payload = await backendJson("/control/source-freshness");
  return payload.datasets || [];
}

export async function getTransformationAudit(runId) {
  const payload = await backendJson(
    `/transformation-audit${buildQuery({ run_id: runId })}`
  );
  return payload.audit || [];
}

export async function getBudgetVariance(budgetName, category, periodLabel) {
  const payload = await backendJson(
    `/reports/budget-variance${buildQuery({
      budget_name: budgetName,
      category_id: category,
      period_label: periodLabel,
    })}`
  );
  return payload.rows || [];
}

export async function getBudgetProgress() {
  const payload = await backendJson("/reports/budget-progress");
  return payload.rows || [];
}

export async function getLoanOverview() {
  const payload = await backendJson("/reports/loan-overview");
  return payload.rows || [];
}

export async function getLoanSchedule(loanId) {
  const payload = await backendJson(`/reports/loan-schedule/${encodeURIComponent(loanId)}`);
  return payload.rows || [];
}

export async function getLoanVariance(loanId) {
  const payload = await backendJson(
    `/reports/loan-variance${buildQuery({ loan_id: loanId })}`
  );
  return payload.rows || [];
}

export async function getHouseholdCostModel(periodLabel, costType) {
  const payload = await backendJson(
    `/reports/household-cost-model${buildQuery({
      period_label: periodLabel,
      cost_type: costType,
    })}`
  );
  return payload.rows || [];
}

export async function getCostTrend() {
  const payload = await backendJson("/reports/cost-trend");
  return payload.rows || [];
}

export async function getAffordabilityRatios() {
  const payload = await backendJson("/reports/affordability-ratios");
  return payload.rows || [];
}

export async function getRecurringCostBaseline() {
  const payload = await backendJson("/reports/recurring-cost-baseline");
  return payload.rows || [];
}
