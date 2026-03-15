import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

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
    const error =
      response.status === 429 ? "locked-out" : "invalid-credentials";
    return NextResponse.redirect(new URL(`/login?error=${error}`, request.url), {
      status: 303
    });
  }

  const redirectResponse = NextResponse.redirect(new URL("/", request.url), {
    status: 303
  });
  const setCookie = response.headers.get("set-cookie");
  if (setCookie) {
    redirectResponse.headers.set("set-cookie", setCookie);
  }
  return redirectResponse;
}
