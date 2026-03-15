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

export async function getTransformationPackages() {
  const payload = await backendJson("/config/transformation-packages");
  return payload.transformation_packages || [];
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

export async function getTransformationAudit(runId) {
  const payload = await backendJson(
    `/transformation-audit${buildQuery({ run_id: runId })}`
  );
  return payload.audit || [];
}
