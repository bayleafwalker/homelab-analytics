// @ts-check

import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

/** @param {Request} request */
export async function POST(request) {
  const formData = await request.formData();
  const response = await backendRequest("post", "/config/source-systems", {
    cookieHeader: request.headers.get("cookie") || "",
    body: {
      source_system_id: String(formData.get("source_system_id") || ""),
      name: String(formData.get("name") || ""),
      source_type: String(formData.get("source_type") || ""),
      transport: String(formData.get("transport") || ""),
      schedule_mode: String(formData.get("schedule_mode") || ""),
      description: String(formData.get("description") || "") || null,
      enabled: String(formData.get("enabled") || "true") === "true"
    }
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
