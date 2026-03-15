import { cookies } from "next/headers";
import { redirect } from "next/navigation";

const API_BASE_URL =
  process.env.HOMELAB_ANALYTICS_API_BASE_URL || "http://127.0.0.1:8080";
const CSRF_COOKIE_NAME = "homelab_analytics_csrf";

export function getApiBaseUrl() {
  return API_BASE_URL.replace(/\/$/, "");
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
  const payload = await backendJson(`/runs?limit=${limit}`);
  return payload.runs || [];
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

export async function getDatasetContracts() {
  const payload = await backendJson("/config/dataset-contracts");
  return payload.dataset_contracts || [];
}

export async function getColumnMappings() {
  const payload = await backendJson("/config/column-mappings");
  return payload.column_mappings || [];
}

export async function getTransformationPackages() {
  const payload = await backendJson("/config/transformation-packages");
  return payload.transformation_packages || [];
}

export async function getSourceAssets() {
  const payload = await backendJson("/config/source-assets");
  return payload.source_assets || [];
}

export async function getIngestionDefinitions() {
  const payload = await backendJson("/config/ingestion-definitions");
  return payload.ingestion_definitions || [];
}

export async function getExecutionSchedules() {
  const payload = await backendJson("/config/execution-schedules");
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

export async function getSourceLineage() {
  const payload = await backendJson("/control/source-lineage");
  return payload.lineage || [];
}

export async function getPublicationAudit() {
  const payload = await backendJson("/control/publication-audit");
  return payload.publication_audit || [];
}

export async function getScheduleDispatches() {
  const payload = await backendJson("/control/schedule-dispatches");
  return payload.dispatches || [];
}
