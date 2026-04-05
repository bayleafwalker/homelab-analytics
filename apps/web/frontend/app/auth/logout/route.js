// @ts-check

import { NextResponse } from "next/server";

import { backendRequest, copyBackendSetCookies } from "@/lib/backend";

/** @param {Request} request */
export async function POST(request) {
  const response = await backendRequest("post", "/auth/logout", {
    cookieHeader: request.headers.get("cookie") || ""
  });
  const redirectResponse = NextResponse.redirect(new URL("/login", request.url), {
    status: 303
  });
  copyBackendSetCookies(response, redirectResponse.headers);
  return redirectResponse;
}
