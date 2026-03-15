import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

export async function POST(request) {
  const payload = await request.json();
  const response = await backendRequest("/auth/service-tokens", {
    method: "POST",
    cookieHeader: request.headers.get("cookie") || "",
    contentType: "application/json",
    body: JSON.stringify(payload)
  });
  return NextResponse.json(await response.json(), { status: response.status });
}
