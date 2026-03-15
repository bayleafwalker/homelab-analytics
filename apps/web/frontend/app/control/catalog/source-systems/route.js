import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

export async function POST(request) {
  const formData = await request.formData();
  const response = await backendRequest("/config/source-systems", {
    method: "POST",
    cookieHeader: request.headers.get("cookie") || "",
    contentType: "application/json",
    body: JSON.stringify({
      source_system_id: String(formData.get("source_system_id") || ""),
      name: String(formData.get("name") || ""),
      source_type: String(formData.get("source_type") || ""),
      transport: String(formData.get("transport") || ""),
      schedule_mode: String(formData.get("schedule_mode") || ""),
      description: String(formData.get("description") || "") || null
    })
  });

  if (!response.ok) {
    return NextResponse.redirect(
      new URL("/control/catalog?error=source-system-failed", request.url),
      { status: 303 }
    );
  }
  return NextResponse.redirect(
    new URL("/control/catalog?notice=source-system-created", request.url),
    { status: 303 }
  );
}
