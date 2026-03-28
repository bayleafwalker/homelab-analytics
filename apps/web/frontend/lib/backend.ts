import createClient, { type MaybeOptionalInit } from "openapi-fetch";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import type {
  ErrorResponseJSON,
  HttpMethod,
  OperationRequestBodyContent,
  PathsWithMethod,
  RequiredKeysOf,
  SuccessResponseJSON
} from "openapi-typescript-helpers";

import type { paths } from "../generated/api";

const API_BASE_URL =
  process.env.HOMELAB_ANALYTICS_API_BASE_URL || "http://127.0.0.1:8080";
const CSRF_COOKIE_NAME = "homelab_analytics_csrf";

type GetApiPath = PathsWithMethod<paths, "get">;
type GetOperation<Path extends GetApiPath> = NonNullable<paths[Path]["get"]>;
type ApiMethod = HttpMethod;
type ApiPathForMethod<Method extends ApiMethod> = PathsWithMethod<paths, Method>;
type OperationForMethodPath<
  Method extends ApiMethod,
  Path extends ApiPathForMethod<Method>
> = NonNullable<paths[Path][Method]>;
type JsonResponseForPath<Path extends GetApiPath> =
  | SuccessResponseJSON<GetOperation<Path>>
  | null;
export type RequestBodyForMethodPath<
  Method extends ApiMethod,
  Path extends ApiPathForMethod<Method>
> = OperationRequestBodyContent<OperationForMethodPath<Method, Path>>;
export type JsonSuccessResponseForMethodPath<
  Method extends ApiMethod,
  Path extends ApiPathForMethod<Method>
> = SuccessResponseJSON<OperationForMethodPath<Method, Path>> | null;
export type JsonErrorResponseForMethodPath<
  Method extends ApiMethod,
  Path extends ApiPathForMethod<Method>
> = ErrorResponseJSON<OperationForMethodPath<Method, Path>> | null;
type ParametersForPath<Path extends GetApiPath> = GetOperation<Path> extends {
  parameters: infer Parameters;
}
  ? Parameters
  : never;
type BackendGetInit<Path extends GetApiPath> = MaybeOptionalInit<paths[Path], "get">;
type BackendOperationInit<
  Method extends ApiMethod,
  Path extends ApiPathForMethod<Method>
> = MaybeOptionalInit<paths[Path], Method>;
type BackendOperationRequestInit<
  Method extends ApiMethod,
  Path extends ApiPathForMethod<Method>
> = Omit<
  NonNullable<BackendOperationInit<Method, Path>>,
  "baseUrl" | "bodySerializer" | "fetch" | "headers" | "parseAs" | "querySerializer"
> & {
  cookieHeader?: string;
  headers?: HeadersInit;
};
type BackendGetArguments<Path extends GetApiPath> = RequiredKeysOf<BackendGetInit<Path>> extends never
  ? [(BackendGetInit<Path> & Record<string, unknown>)?]
  : [BackendGetInit<Path> & Record<string, unknown>];
type BackendOperationArguments<
  Method extends ApiMethod,
  Path extends ApiPathForMethod<Method>
> = RequiredKeysOf<BackendOperationInit<Method, Path>> extends never
  ? [(BackendOperationRequestInit<Method, Path> & Record<string, unknown>)?]
  : [BackendOperationRequestInit<Method, Path> & Record<string, unknown>];
type QueryParamsForPath<Path extends GetApiPath> = ParametersForPath<Path> extends {
  query?: infer Query;
}
  ? Query
  : never;
type PathParamsForPath<Path extends GetApiPath> = ParametersForPath<Path> extends {
  path: infer PathParams;
}
  ? PathParams
  : never;
type QueryValue<
  Path extends GetApiPath,
  Key extends keyof QueryParamsForPath<Path>
> = QueryParamsForPath<Path>[Key];
type PathValue<
  Path extends GetApiPath,
  Key extends keyof PathParamsForPath<Path>
> = PathParamsForPath<Path>[Key];
type ResponseField<Response, Field extends string> = Response extends Record<Field, infer Value>
  ? Value
  : unknown;
type PresentResponseField<Response, Field extends string> = Exclude<
  ResponseField<Response, Field>,
  null | undefined
>;
type ResponseArrayField<Response, Field extends string> =
  PresentResponseField<Response, Field> extends ReadonlyArray<unknown>
    ? PresentResponseField<Response, Field>
    : unknown[];
type FirstResponseArrayItem<Response, Field extends string> =
  ResponseArrayField<Response, Field> extends ReadonlyArray<infer Item>
    ? Item | null
    : unknown | null;
type DefinedValues<T extends Record<string, unknown>> = {
  [Key in keyof T as Exclude<T[Key], undefined> extends never ? never : Key]?: Exclude<
    T[Key],
    undefined
  >;
};
type RawBackendRequestOptions = {
  method?: string;
  headers?: HeadersInit;
  body?: BodyInit | null;
  cookieHeader?: string;
  contentType?: string;
};
type BackendJsonRequestResult<
  Method extends ApiMethod,
  Path extends ApiPathForMethod<Method>
> = {
  response: Response;
  data: JsonSuccessResponseForMethodPath<Method, Path>;
  error: JsonErrorResponseForMethodPath<Method, Path>;
};

export function getApiBaseUrl() {
  return API_BASE_URL.replace(/\/$/, "");
}

function getCookieValue(cookieHeader: string, name: string) {
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

function createBackendFetch(
  cookieHeader: string = "",
  headers: HeadersInit = {}
) {
  return async (input: RequestInfo | URL, init?: RequestInit) => {
    const outboundHeaders = new Headers(init?.headers || headers);
    const currentCookies = cookieHeader || cookies().toString();
    if (currentCookies) {
      outboundHeaders.set("cookie", currentCookies);
    }
    if (!["GET", "HEAD", "OPTIONS"].includes(String(init?.method || "GET").toUpperCase())) {
      const csrfToken = getCookieValue(currentCookies, CSRF_COOKIE_NAME);
      if (csrfToken) {
        outboundHeaders.set("x-csrf-token", csrfToken);
      }
    }
    return fetch(input, {
      ...init,
      cache: "no-store",
      headers: outboundHeaders,
      redirect: "manual"
    });
  };
}

function createBackendClient(
  cookieHeader: string = "",
  headers: HeadersInit = {}
) {
  return createClient<paths, "application/json">({
    baseUrl: getApiBaseUrl(),
    fetch: createBackendFetch(cookieHeader, headers)
  });
}

function buildQueryString(query?: Record<string, unknown>) {
  if (!query) {
    return "";
  }
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value == null) {
      continue;
    }
    if (Array.isArray(value)) {
      for (const item of value) {
        if (item != null) {
          searchParams.append(key, String(item));
        }
      }
      continue;
    }
    searchParams.append(key, String(value));
  }
  const queryString = searchParams.toString();
  return queryString ? `?${queryString}` : "";
}

function buildOperationPath(
  pathTemplate: string,
  params?: {
    path?: Record<string, unknown>;
    query?: Record<string, unknown>;
  }
) {
  const resolvedPath = pathTemplate.replace(/\{([^}]+)\}/g, (_, key: string) => {
    const value = params?.path?.[key];
    if (value == null) {
      throw new Error(`Missing path parameter "${key}" for ${pathTemplate}`);
    }
    return encodeURIComponent(String(value));
  });
  return `${resolvedPath}${buildQueryString(params?.query)}`;
}

function isBodyInitValue(body: unknown): body is BodyInit {
  return (
    typeof body === "string" ||
    body instanceof FormData ||
    body instanceof URLSearchParams ||
    body instanceof Blob ||
    body instanceof ArrayBuffer ||
    ArrayBuffer.isView(body)
  );
}

export async function backendRequest(
  path: string,
  options?: RawBackendRequestOptions
): Promise<Response>;
export async function backendRequest<
  Method extends ApiMethod,
  Path extends ApiPathForMethod<Method>
>(
  method: Method,
  path: Path,
  ...args: BackendOperationArguments<Method, Path>
): Promise<Response>;
export async function backendRequest<
  Method extends ApiMethod,
  Path extends ApiPathForMethod<Method>
>(
  first: string,
  second?: string | RawBackendRequestOptions,
  ...rest: unknown[]
): Promise<Response> {
  if (typeof second === "string") {
    const method = first as Method;
    const path = second as Path;
    const {
      cookieHeader = "",
      headers = {},
      body,
      params,
      ...requestInit
    } = (rest[0] ?? {}) as BackendOperationRequestInit<Method, Path>;
    const outboundHeaders = new Headers(headers);
    let requestBody: BodyInit | null | undefined;
    if (body !== undefined) {
      if (isBodyInitValue(body)) {
        requestBody = body;
      } else {
        requestBody = JSON.stringify(body);
        if (!outboundHeaders.has("content-type")) {
          outboundHeaders.set("content-type", "application/json");
        }
      }
    }
    const backendFetch = createBackendFetch(cookieHeader, outboundHeaders);
    const fetchInit: RequestInit = {
      ...(requestInit as RequestInit),
      method: method.toUpperCase()
    };
    if (requestBody !== undefined) {
      fetchInit.body = requestBody;
    }
    return backendFetch(`${getApiBaseUrl()}${buildOperationPath(path, params)}`, fetchInit);
  }

  return rawBackendRequest(first, second as RawBackendRequestOptions | undefined);
}

async function rawBackendRequest(
  path: string,
  {
    method = "GET",
    headers = {},
    body,
    cookieHeader,
    contentType
  }: RawBackendRequestOptions = {}
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
  const requestInit: RequestInit = {
    method,
    headers: outboundHeaders,
    cache: "no-store",
    redirect: "manual"
  };
  if (body !== undefined) {
    requestInit.body = body;
  }
  return fetch(`${getApiBaseUrl()}${path}`, requestInit);
}

export async function backendJsonRequest<
  Method extends ApiMethod,
  Path extends ApiPathForMethod<Method>
>(
  method: Method,
  path: Path,
  ...args: BackendOperationArguments<Method, Path>
): Promise<BackendJsonRequestResult<Method, Path>> {
  const {
    cookieHeader = "",
    headers = {},
    ...requestInit
  } = (args[0] ?? {}) as BackendOperationRequestInit<Method, Path>;
  const response = await backendRequest(method, path, {
    ...(requestInit as BackendOperationRequestInit<Method, Path>),
    cookieHeader,
    headers
  });
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (response.ok) {
    return {
      response,
      data: payload as JsonSuccessResponseForMethodPath<Method, Path>,
      error: null
    };
  }

  return {
    response,
    data: null,
    error: payload as JsonErrorResponseForMethodPath<Method, Path>
  };
}

export function copyBackendSetCookies(sourceResponse: Response, targetHeaders: Headers) {
  const getSetCookie = sourceResponse.headers.getSetCookie?.bind(sourceResponse.headers);
  const cookieValues = getSetCookie
    ? getSetCookie()
    : [sourceResponse.headers.get("set-cookie")].filter(
        (value): value is string => Boolean(value)
      );
  for (const cookieValue of cookieValues) {
    targetHeaders.append("set-cookie", cookieValue);
  }
}

function getResponseField<Response, Field extends string>(
  response: Response,
  field: Field
): ResponseField<Response, Field> {
  if (response && typeof response === "object") {
    return (response as Record<string, unknown>)[field] as ResponseField<Response, Field>;
  }
  return undefined as ResponseField<Response, Field>;
}

function getResponseFieldOrFallback<Response, Field extends string, Fallback>(
  response: Response,
  field: Field,
  fallback: Fallback
): PresentResponseField<Response, Field> | Fallback {
  const value = getResponseField(response, field);
  return value == null ? fallback : (value as PresentResponseField<Response, Field>);
}

function getResponseArray<Response, Field extends string>(
  response: Response,
  field: Field
): ResponseArrayField<Response, Field> {
  const value = getResponseField(response, field);
  return Array.isArray(value)
    ? (value as ResponseArrayField<Response, Field>)
    : ([] as ResponseArrayField<Response, Field>);
}

function getFirstResponseArrayItem<Response, Field extends string>(
  response: Response,
  field: Field
): FirstResponseArrayItem<Response, Field> {
  const value = getResponseArray(response, field);
  return (value[0] ?? null) as FirstResponseArrayItem<Response, Field>;
}

function definedValues<T extends Record<string, unknown>>(values: T): DefinedValues<T> {
  return Object.fromEntries(
    Object.entries(values).filter(([, value]) => value !== undefined)
  ) as DefinedValues<T>;
}

async function backendGet<Path extends GetApiPath>(
  path: Path,
  ...args: BackendGetArguments<Path>
): Promise<JsonResponseForPath<Path>> {
  const client = createBackendClient();
  const response = await client.GET(path, ...args);
  if (response.response.status === 401) {
    redirect("/login");
  }
  if (!response.response.ok) {
    throw new Error(`Backend request failed for ${path}: ${response.response.status}`);
  }
  if (response.data === undefined) {
    throw new Error(`Backend request returned no JSON body for ${path}`);
  }
  return response.data as JsonResponseForPath<Path>;
}

export async function getCurrentUser() {
  const payload = await backendGet("/auth/me");
  return getResponseField(payload, "user");
}

type RunsPageOptions = {
  dataset?: QueryValue<"/runs", "dataset">;
  status?: QueryValue<"/runs", "status">;
  fromDate?: QueryValue<"/runs", "from_date">;
  toDate?: QueryValue<"/runs", "to_date">;
  limit?: QueryValue<"/runs", "limit">;
  offset?: QueryValue<"/runs", "offset">;
};

export async function getRuns(limit: QueryValue<"/runs", "limit"> = 8) {
  const payload = await backendGet("/runs", { params: { query: { limit } } });
  return getResponseArray(payload, "runs");
}

export async function getRunsPage({
  dataset,
  status,
  fromDate,
  toDate,
  limit = 50,
  offset = 0
}: RunsPageOptions = {}) {
  return backendGet("/runs", {
    params: {
      query: definedValues({
        dataset,
        status,
        from_date: fromDate,
        to_date: toDate,
        limit,
        offset
      })
    }
  });
}

export async function getRun(runId: PathValue<"/runs/{run_id}", "run_id">) {
  const payload = await backendGet("/runs/{run_id}", {
    params: { path: { run_id: runId } }
  });
  return getResponseField(payload, "run");
}

export async function getHouseholdOverview() {
  const payload = await backendGet("/reports/household-overview");
  return getFirstResponseArrayItem(payload, "rows");
}
export async function getAttentionItems() {
  const payload = await backendGet("/reports/attention-items");
  return getResponseArray(payload, "rows");
}
export async function getRecentChanges() {
  const payload = await backendGet("/reports/recent-changes");
  return getResponseArray(payload, "rows");
}
export async function getSpendByCategoryMonthly() {
  const payload = await backendGet("/reports/spend-by-category-monthly");
  return getResponseArray(payload, "rows");
}
export async function getRecentLargeTransactions() {
  const payload = await backendGet("/reports/recent-large-transactions");
  return getResponseArray(payload, "rows");
}
export async function getAccountBalanceTrend() {
  const payload = await backendGet("/reports/account-balance-trend");
  return getResponseArray(payload, "rows");
}
export async function getTransactionAnomalies() {
  const payload = await backendGet("/reports/transaction-anomalies");
  return getResponseArray(payload, "rows");
}
export async function getUpcomingFixedCosts() {
  const payload = await backendGet("/reports/upcoming-fixed-costs");
  return getResponseArray(payload, "rows");
}
export async function getUtilityCostTrend(
  utilityType: QueryValue<"/reports/utility-cost-trend", "utility_type">
) {
  const payload = await backendGet("/reports/utility-cost-trend", {
    params: { query: definedValues({ utility_type: utilityType }) }
  });
  return getResponseArray(payload, "rows");
}

export async function getUtilityCostSummary(
  utilityType: QueryValue<"/reports/utility-cost-summary", "utility_type">,
  meterId: QueryValue<"/reports/utility-cost-summary", "meter_id">,
  fromPeriod: QueryValue<"/reports/utility-cost-summary", "from_period">,
  toPeriod: QueryValue<"/reports/utility-cost-summary", "to_period">
) {
  const payload = await backendGet("/reports/utility-cost-summary", {
    params: {
      query: definedValues({
        utility_type: utilityType,
        meter_id: meterId,
        from_period: fromPeriod,
        to_period: toPeriod
      })
    }
  });
  return getResponseArray(payload, "rows");
}

export async function getUsageVsPrice(
  utilityType: QueryValue<"/reports/usage-vs-price", "utility_type">
) {
  const payload = await backendGet("/reports/usage-vs-price", {
    params: { query: definedValues({ utility_type: utilityType }) }
  });
  return getResponseArray(payload, "rows");
}
export async function getContractReviewCandidates() {
  const payload = await backendGet("/reports/contract-review-candidates");
  return getResponseArray(payload, "rows");
}
export async function getContractRenewalWatchlist() {
  const payload = await backendGet("/reports/contract-renewal-watchlist");
  return getResponseArray(payload, "rows");
}
export async function getSubscriptionSummary() {
  const payload = await backendGet("/reports/subscription-summary");
  return getResponseArray(payload, "rows");
}
export async function getCategoryDimension() {
  const payload = await backendGet("/reports/current-dimensions/{dimension_name}", {
    params: { path: { dimension_name: "dim_category" } }
  });
  return getResponseArray(payload, "rows");
}

export async function getMonthlyCashflow() {
  const payload = await backendGet("/reports/monthly-cashflow");
  return getResponseArray(payload, "rows");
}

export async function getPublicationContracts() {
  const payload = await backendGet("/contracts/publications");
  return getResponseArray(payload, "publication_contracts");
}

export async function getPublicationContract(
  publicationKey: PathValue<
    "/contracts/publications/{publication_key}",
    "publication_key"
  >
) {
  return backendGet("/contracts/publications/{publication_key}", {
    params: { path: { publication_key: publicationKey } }
  });
}

export async function getUiDescriptors() {
  const payload = await backendGet("/contracts/ui-descriptors");
  return getResponseArray(payload, "ui_descriptors");
}

export async function getSourceSystems() {
  const payload = await backendGet("/config/source-systems");
  return getResponseArray(payload, "source_systems");
}

export async function getDatasetContracts({ includeArchived = false } = {}) {
  const payload = await backendGet("/config/dataset-contracts", {
    params: { query: { include_archived: includeArchived } }
  });
  return getResponseArray(payload, "dataset_contracts");
}

export async function getDatasetContractDiff(
  leftId: PathValue<"/config/dataset-contracts/{dataset_contract_id}/diff", "dataset_contract_id">,
  rightId: QueryValue<"/config/dataset-contracts/{dataset_contract_id}/diff", "other_id">
) {
  const payload = await backendGet("/config/dataset-contracts/{dataset_contract_id}/diff", {
    params: {
      path: { dataset_contract_id: leftId },
      query: { other_id: rightId }
    }
  });
  return getResponseField(payload, "diff");
}

export async function getColumnMappings({ includeArchived = false } = {}) {
  const payload = await backendGet("/config/column-mappings", {
    params: { query: { include_archived: includeArchived } }
  });
  return getResponseArray(payload, "column_mappings");
}

export async function getColumnMappingDiff(
  leftId: PathValue<"/config/column-mappings/{column_mapping_id}/diff", "column_mapping_id">,
  rightId: QueryValue<"/config/column-mappings/{column_mapping_id}/diff", "other_id">
) {
  const payload = await backendGet("/config/column-mappings/{column_mapping_id}/diff", {
    params: {
      path: { column_mapping_id: leftId },
      query: { other_id: rightId }
    }
  });
  return getResponseField(payload, "diff");
}

export async function getTransformationHandlers() {
  const payload = await backendGet("/config/transformation-handlers");
  return getResponseArray(payload, "transformation_handlers");
}

export async function getPublicationKeys() {
  const payload = await backendGet("/config/publication-keys");
  return getResponseArray(payload, "publication_keys");
}

export async function getExtensionRegistrySources({ includeArchived = false } = {}) {
  const payload = await backendGet("/config/extension-registry-sources", {
    params: { query: { include_archived: includeArchived } }
  });
  return getResponseArray(payload, "extension_registry_sources");
}

type ExtensionRegistryRevisionOptions = {
  extensionRegistrySourceId?: QueryValue<
    "/config/extension-registry-revisions",
    "extension_registry_source_id"
  >;
};

export async function getExtensionRegistryRevisions({
  extensionRegistrySourceId
}: ExtensionRegistryRevisionOptions = {}) {
  const payload = await backendGet("/config/extension-registry-revisions", {
    params: {
      query: definedValues({
        extension_registry_source_id: extensionRegistrySourceId
      })
    }
  });
  return getResponseArray(payload, "extension_registry_revisions");
}

export async function getExtensionRegistryActivations() {
  const payload = await backendGet("/config/extension-registry-activations");
  return getResponseArray(payload, "extension_registry_activations");
}

export async function getFunctions() {
  const payload = await backendGet("/functions");
  return getResponseFieldOrFallback(payload, "functions", {});
}

export async function getHaEntities(
  entityClass: QueryValue<"/api/ha/entities", "entity_class"> = null
) {
  const payload = await backendGet("/api/ha/entities", {
    params: { query: { entity_class: entityClass } }
  });
  return getResponseArray(payload, "rows");
}

export async function getHaEntityHistory(
  entityId: PathValue<"/api/ha/entities/{entity_id}/history", "entity_id">,
  limit: QueryValue<"/api/ha/entities/{entity_id}/history", "limit"> = 50
) {
  const payload = await backendGet("/api/ha/entities/{entity_id}/history", {
    params: {
      path: { entity_id: entityId },
      query: { limit }
    }
  });
  return getResponseArray(payload, "rows");
}

export async function getHaBridgeStatus() {
  return backendGet("/api/ha/bridge/status");
}

export async function getHaMqttStatus() {
  return backendGet("/api/ha/mqtt/status");
}

export async function getHaPolicies() {
  const payload = await backendGet("/api/ha/policies");
  return getResponseArray(payload, "policies");
}

export async function getHaActions(
  limit: QueryValue<"/api/ha/actions", "limit"> = 50
) {
  const payload = await backendGet("/api/ha/actions", {
    params: { query: { limit } }
  });
  return getResponseArray(payload, "actions");
}

export async function getHaActionsStatus() {
  return backendGet("/api/ha/actions/status");
}

export async function getHaActionProposals() {
  const payload = await backendGet("/api/ha/actions/proposals");
  return getResponseArray(payload, "proposals");
}

export async function getTransformationPackages({ includeArchived = false } = {}) {
  const payload = await backendGet("/config/transformation-packages", {
    params: { query: { include_archived: includeArchived } }
  });
  return getResponseArray(payload, "transformation_packages");
}

type PublicationDefinitionOptions = {
  transformationPackageId?: QueryValue<
    "/config/publication-definitions",
    "transformation_package_id"
  >;
  includeArchived?: QueryValue<"/config/publication-definitions", "include_archived">;
};

export async function getPublicationDefinitions({
  transformationPackageId,
  includeArchived = false
}: PublicationDefinitionOptions = {}) {
  const payload = await backendGet("/config/publication-definitions", {
    params: {
      query: definedValues({
        transformation_package_id: transformationPackageId,
        include_archived: includeArchived
      })
    }
  });
  return getResponseArray(payload, "publication_definitions");
}

export async function getSourceAssets({ includeArchived = false } = {}) {
  const payload = await backendGet("/config/source-assets", {
    params: { query: { include_archived: includeArchived } }
  });
  return getResponseArray(payload, "source_assets");
}

export async function getIngestionDefinitions({ includeArchived = false } = {}) {
  const payload = await backendGet("/config/ingestion-definitions", {
    params: { query: { include_archived: includeArchived } }
  });
  return getResponseArray(payload, "ingestion_definitions");
}

export async function getExecutionSchedules({ includeArchived = false } = {}) {
  const payload = await backendGet("/config/execution-schedules", {
    params: { query: { include_archived: includeArchived } }
  });
  return getResponseArray(payload, "execution_schedules");
}

export async function getLocalUsers() {
  const payload = await backendGet("/auth/users");
  return getResponseArray(payload, "users");
}

export async function getServiceTokens({ includeRevoked = false } = {}) {
  const payload = await backendGet("/auth/service-tokens", {
    params: { query: { include_revoked: includeRevoked } }
  });
  return getResponseArray(payload, "service_tokens");
}

export async function getAuthAuditEvents(
  limit: QueryValue<"/control/auth-audit", "limit"> = 30
) {
  const payload = await backendGet("/control/auth-audit", {
    params: { query: { limit } }
  });
  return getResponseArray(payload, "auth_audit_events");
}

type SourceLineageOptions = {
  runId?: QueryValue<"/control/source-lineage", "run_id">;
  targetLayer?: QueryValue<"/control/source-lineage", "target_layer">;
};

export async function getSourceLineage({
  runId,
  targetLayer
}: SourceLineageOptions = {}) {
  const payload = await backendGet("/control/source-lineage", {
    params: {
      query: definedValues({
        run_id: runId,
        target_layer: targetLayer
      })
    }
  });
  return getResponseArray(payload, "lineage");
}

type PublicationAuditOptions = {
  runId?: QueryValue<"/control/publication-audit", "run_id">;
  publicationKey?: QueryValue<"/control/publication-audit", "publication_key">;
};

export async function getPublicationAudit({
  runId,
  publicationKey
}: PublicationAuditOptions = {}) {
  const payload = await backendGet("/control/publication-audit", {
    params: {
      query: definedValues({
        run_id: runId,
        publication_key: publicationKey
      })
    }
  });
  return getResponseArray(payload, "publication_audit");
}

type ScheduleDispatchOptions = {
  scheduleId?: QueryValue<"/control/schedule-dispatches", "schedule_id">;
  status?: QueryValue<"/control/schedule-dispatches", "status">;
};

export async function getScheduleDispatches({
  scheduleId,
  status
}: ScheduleDispatchOptions = {}) {
  const payload = await backendGet("/control/schedule-dispatches", {
    params: {
      query: definedValues({
        schedule_id: scheduleId,
        status
      })
    }
  });
  return getResponseArray(payload, "dispatches");
}

export async function getScheduleDispatch(
  dispatchId: PathValue<"/control/schedule-dispatches/{dispatch_id}", "dispatch_id">
) {
  return backendGet("/control/schedule-dispatches/{dispatch_id}", {
    params: { path: { dispatch_id: dispatchId } }
  });
}

export async function getOperationalSummary() {
  return backendGet("/control/operational-summary");
}

export async function getTerminalCommands() {
  const payload = await backendGet("/control/terminal/commands");
  return getResponseArray(payload, "commands");
}

export async function getSourceFreshness() {
  const payload = await backendGet("/control/source-freshness");
  return getResponseArray(payload, "datasets");
}

export async function getTransformationAudit(
  runId: QueryValue<"/transformation-audit", "run_id">
) {
  const payload = await backendGet("/transformation-audit", {
    params: { query: definedValues({ run_id: runId }) }
  });
  return getResponseArray(payload, "rows");
}

export async function getBudgetVariance(
  budgetName: QueryValue<"/reports/budget-variance", "budget_name">,
  category: QueryValue<"/reports/budget-variance", "category_id">,
  periodLabel: QueryValue<"/reports/budget-variance", "period_label">
) {
  const payload = await backendGet("/reports/budget-variance", {
    params: {
      query: definedValues({
        budget_name: budgetName,
        category_id: category,
        period_label: periodLabel
      })
    }
  });
  return getResponseArray(payload, "rows");
}

export async function getBudgetProgress() {
  const payload = await backendGet("/reports/budget-progress");
  return getResponseArray(payload, "rows");
}

export async function getLoanOverview() {
  const payload = await backendGet("/reports/loan-overview");
  return getResponseArray(payload, "rows");
}

export async function getLoanSchedule(
  loanId: PathValue<"/reports/loan-schedule/{loan_id}", "loan_id">
) {
  const payload = await backendGet("/reports/loan-schedule/{loan_id}", {
    params: { path: { loan_id: loanId } }
  });
  return getResponseArray(payload, "rows");
}

export async function getLoanVariance(
  loanId: QueryValue<"/reports/loan-variance", "loan_id">
) {
  const payload = await backendGet("/reports/loan-variance", {
    params: { query: definedValues({ loan_id: loanId }) }
  });
  return getResponseArray(payload, "rows");
}

export async function getHouseholdCostModel(
  periodLabel: QueryValue<"/reports/household-cost-model", "period_label">,
  costType: QueryValue<"/reports/household-cost-model", "cost_type">
) {
  const payload = await backendGet("/reports/household-cost-model", {
    params: {
      query: definedValues({
        period_label: periodLabel,
        cost_type: costType
      })
    }
  });
  return getResponseArray(payload, "rows");
}

export async function getCostTrend() {
  const payload = await backendGet("/reports/cost-trend");
  return getResponseArray(payload, "rows");
}

export async function getAffordabilityRatios() {
  const payload = await backendGet("/reports/affordability-ratios");
  return getResponseArray(payload, "rows");
}

export async function getRecurringCostBaseline() {
  const payload = await backendGet("/reports/recurring-cost-baseline");
  return getResponseArray(payload, "rows");
}

export async function getScenarios({ includeArchived = false } = {}) {
  const payload = await backendGet("/api/scenarios", {
    params: { query: { include_archived: includeArchived } }
  });
  return getResponseArray(payload, "rows");
}

export async function getScenarioMetadata(
  scenarioId: PathValue<"/api/scenarios/{scenario_id}", "scenario_id">
) {
  return backendGet("/api/scenarios/{scenario_id}", {
    params: { path: { scenario_id: scenarioId } }
  });
}

export async function getScenarioComparison(
  scenarioId: PathValue<"/api/scenarios/{scenario_id}/comparison", "scenario_id">
) {
  return backendGet("/api/scenarios/{scenario_id}/comparison", {
    params: { path: { scenario_id: scenarioId } }
  });
}

export async function getScenarioCashflow(
  scenarioId: PathValue<"/api/scenarios/{scenario_id}/cashflow", "scenario_id">
) {
  return backendGet("/api/scenarios/{scenario_id}/cashflow", {
    params: { path: { scenario_id: scenarioId } }
  });
}
