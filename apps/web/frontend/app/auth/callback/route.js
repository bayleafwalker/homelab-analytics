// @ts-check

import { NextResponse } from "next/server";

import { backendRequest, copyBackendSetCookies } from "@/lib/backend";

/** @param {import("next/server").NextRequest} request */
export async function GET(request) {
  const code = request.nextUrl.searchParams.get("code");
  const state = request.nextUrl.searchParams.get("state");
  const error = request.nextUrl.searchParams.get("error");
  const response = await backendRequest("get", "/auth/callback", {
    cookieHeader: request.headers.get("cookie") || "",
    params: {
      query: {
        ...(code !== null ? { code } : {}),
        ...(state !== null ? { state } : {}),
        ...(error !== null ? { error } : {})
      }
    }
  });
  const location = response.headers.get("location") || "/login?error=oidc-failed";
  const redirectResponse = NextResponse.redirect(new URL(location, request.url), {
    status: response.status === 302 || response.status === 303 ? response.status : 303
  });
  copyBackendSetCookies(response, redirectResponse.headers);
  return redirectResponse;
}
