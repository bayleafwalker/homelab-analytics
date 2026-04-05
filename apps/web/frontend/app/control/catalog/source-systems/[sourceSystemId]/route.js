// @ts-check

import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

/**
 * @param {Request} request
 * @param {{ params: { sourceSystemId: string } }} context
 */
export async function POST(request, { params }) {
  const formData = await request.formData();
  const response = await backendRequest("patch", "/config/source-systems/{source_system_id}", {
    cookieHeader: request.headers.get("cookie") || "",
    params: { path: { source_system_id: params.sourceSystemId } },
    body: {
      source_system_id: String(formData.get("source_system_id") || params.sourceSystemId || ""),
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
      new URL("/control/catalog?error=source-system-update-failed", request.url),
      { status: 303 }
    );
  }
  return NextResponse.redirect(
    new URL("/control/catalog?notice=source-system-updated", request.url),
    { status: 303 }
  );
}
