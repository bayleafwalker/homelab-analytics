import { NextResponse } from "next/server";

import { backendRequest, copyBackendSetCookies } from "@/lib/backend";

function redirectWithBackendCookies(response, request, fallbackPath) {
  const location = response.headers.get("location") || fallbackPath;
  const redirectResponse = NextResponse.redirect(new URL(location, request.url), {
    status: response.status === 302 || response.status === 303 ? response.status : 303
  });
  copyBackendSetCookies(response, redirectResponse.headers);
  return redirectResponse;
}

export async function GET(request) {
  const search = request.nextUrl.search || "";
  const response = await backendRequest(`/auth/login${search}`, {
    method: "GET",
    cookieHeader: request.headers.get("cookie") || ""
  });
  return redirectWithBackendCookies(response, request, "/login?error=oidc-failed");
}

export async function POST(request) {
  const formData = await request.formData();
  const username = String(formData.get("username") || "");
  const password = String(formData.get("password") || "");
  const response = await backendRequest("/auth/login", {
    method: "POST",
    cookieHeader: request.headers.get("cookie") || "",
    contentType: "application/json",
    body: JSON.stringify({ username, password })
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
