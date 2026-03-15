import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

export async function POST(request) {
  const payload = await request.json();
  const response = await backendRequest("/config/column-mappings/preview", {
    method: "POST",
    cookieHeader: request.headers.get("cookie") || "",
    contentType: "application/json",
    body: JSON.stringify(payload)
  });
  let body = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  if (!response.ok) {
    return NextResponse.json(
      { error: body?.error || body?.detail || "Preview failed." },
      { status: response.status }
    );
  }
  return NextResponse.json(body || { preview: null }, { status: response.status });
}
