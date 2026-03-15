import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

export async function POST(request) {
  const response = await backendRequest("/auth/logout", {
    method: "POST",
    cookieHeader: request.headers.get("cookie") || ""
  });
  const redirectResponse = NextResponse.redirect(new URL("/login", request.url), {
    status: 303
  });
  const setCookie = response.headers.get("set-cookie");
  if (setCookie) {
    redirectResponse.headers.set("set-cookie", setCookie);
  }
  return redirectResponse;
}
