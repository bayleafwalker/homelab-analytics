import { NextResponse } from "next/server";

import { backendRequest, copyBackendSetCookies } from "@/lib/backend";

export async function POST(request) {
  const response = await backendRequest("/auth/logout", {
    method: "POST",
    cookieHeader: request.headers.get("cookie") || ""
  });
  const redirectResponse = NextResponse.redirect(new URL("/login", request.url), {
    status: 303
  });
  copyBackendSetCookies(response, redirectResponse.headers);
  return redirectResponse;
}
