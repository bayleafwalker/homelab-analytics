// @ts-check

// Same-origin proxy for the scenario API.
//
// The what-if panels (expense shock on /reports, income change, tariff shock,
// loan what-if, homelab cost/benefit, saved compare sets) call
// `/api/scenarios/...` from the browser. The web and API workloads run on
// different origins by default (web :8081, API :8080, no shared reverse
// proxy), so those calls must be forwarded server-side through lib/backend.ts
// with the operator's session cookie and CSRF token, like every other
// browser-initiated mutation in this shell.

import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

const SCENARIO_API_PREFIX = "/api/scenarios";

/**
 * @param {Request} request
 * @param {{ params: { path?: string[] } }} context
 */
async function forward(request, context) {
  const segments = context?.params?.path || [];
  const suffix = segments.map((segment) => encodeURIComponent(segment)).join("/");
  const search = new URL(request.url).search;
  const backendPath = `${SCENARIO_API_PREFIX}${suffix ? `/${suffix}` : ""}${search}`;
  const method = request.method.toUpperCase();
  const hasBody = !["GET", "HEAD", "DELETE"].includes(method);

  /** @type {{ method: string, cookieHeader: string, body?: string, contentType?: string }} */
  const options = { method, cookieHeader: request.headers.get("cookie") || "" };
  if (hasBody) {
    options.body = await request.text();
    options.contentType = request.headers.get("content-type") || "application/json";
  }
  const response = await backendRequest(backendPath, options);

  const bodyless = response.status === 204 || response.status === 304;
  const payload = bodyless ? null : await response.text();
  return new NextResponse(payload, {
    status: response.status,
    headers: {
      "content-type": response.headers.get("content-type") || "application/json"
    }
  });
}

export const GET = forward;
export const POST = forward;
export const PUT = forward;
export const PATCH = forward;
export const DELETE = forward;
