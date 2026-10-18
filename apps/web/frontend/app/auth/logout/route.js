// @ts-check

import { NextResponse } from "next/server";

import { backendRequest, copyBackendSetCookies } from "@/lib/backend";

/**
 * The IdP end-session URL from the backend logout payload, if any.
 *
 * In OIDC mode the backend returns the IdP's end_session_endpoint for an
 * OIDC session (RP-initiated logout). Anything else, including a missing,
 * malformed or non-http(s) value, falls back to the local login page.
 *
 * @param {Response} response
 * @returns {Promise<string | null>}
 */
async function endSessionUrl(response) {
  if (!response.ok) {
    return null;
  }
  try {
    const payload = await response.json();
    const candidate = payload && payload.end_session_url;
    if (typeof candidate !== "string" || !candidate) {
      return null;
    }
    const url = new URL(candidate);
    return url.protocol === "https:" || url.protocol === "http:" ? url.toString() : null;
  } catch {
    return null;
  }
}

/** @param {Request} request */
export async function POST(request) {
  const response = await backendRequest("post", "/auth/logout", {
    cookieHeader: request.headers.get("cookie") || ""
  });
  const target = (await endSessionUrl(response)) || new URL("/login", request.url);
  const redirectResponse = NextResponse.redirect(target, {
    status: 303
  });
  // The app session cookies are cleared before leaving for the IdP.
  copyBackendSetCookies(response, redirectResponse.headers);
  return redirectResponse;
}
