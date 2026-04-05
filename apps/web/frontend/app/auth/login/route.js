// @ts-check

import { NextResponse } from "next/server";

import { backendRequest, copyBackendSetCookies } from "@/lib/backend";

/**
 * @param {Response} response
 * @param {import("next/server").NextRequest} request
 * @param {string} fallbackPath
 */
function redirectWithBackendCookies(response, request, fallbackPath) {
  const location = response.headers.get("location") || fallbackPath;
  const redirectResponse = NextResponse.redirect(new URL(location, request.url), {
    status: response.status === 302 || response.status === 303 ? response.status : 303
  });
  copyBackendSetCookies(response, redirectResponse.headers);
  return redirectResponse;
}

/** @param {import("next/server").NextRequest} request */
export async function GET(request) {
  const returnTo = request.nextUrl.searchParams.get("return_to");
  const response = await backendRequest("get", "/auth/login", {
    cookieHeader: request.headers.get("cookie") || "",
    params: returnTo ? { query: { return_to: returnTo } } : {}
  });
  return redirectWithBackendCookies(response, request, "/login?error=oidc-failed");
}

/** @param {Request} request */
export async function POST(request) {
  const formData = await request.formData();
  const username = String(formData.get("username") || "");
  const password = String(formData.get("password") || "");
  const response = await backendRequest("post", "/auth/login", {
    cookieHeader: request.headers.get("cookie") || "",
    body: { username, password }
  });

  if (response.status !== 200) {
    const error = response.status === 429 ? "locked-out" : "invalid-credentials";
    return NextResponse.redirect(new URL(`/login?error=${error}`, request.url), {
      status: 303
    });
  }

  const redirectResponse = NextResponse.redirect(new URL("/", request.url), {
    status: 303
  });
  copyBackendSetCookies(response, redirectResponse.headers);
  return redirectResponse;
}
