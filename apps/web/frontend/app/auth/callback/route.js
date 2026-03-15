import { NextResponse } from "next/server";

import { backendRequest, copyBackendSetCookies } from "@/lib/backend";

export async function GET(request) {
  const search = request.nextUrl.search || "";
  const response = await backendRequest(`/auth/callback${search}`, {
    method: "GET",
    cookieHeader: request.headers.get("cookie") || ""
  });
  const location = response.headers.get("location") || "/login?error=oidc-failed";
  const redirectResponse = NextResponse.redirect(new URL(location, request.url), {
    status: response.status === 302 || response.status === 303 ? response.status : 303
  });
  copyBackendSetCookies(response, redirectResponse.headers);
  return redirectResponse;
}
