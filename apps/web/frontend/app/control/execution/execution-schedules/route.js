import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

function parseInteger(value, fallback) {
  const parsed = Number.parseInt(String(value || ""), 10);
  return Number.isNaN(parsed) ? fallback : parsed;
}

export async function POST(request) {
  const formData = await request.formData();
  const response = await backendRequest("/config/execution-schedules", {
    method: "POST",
    cookieHeader: request.headers.get("cookie") || "",
    contentType: "application/json",
    body: JSON.stringify({
      schedule_id: String(formData.get("schedule_id") || ""),
      target_kind: String(formData.get("target_kind") || ""),
      target_ref: String(formData.get("target_ref") || ""),
      cron_expression: String(formData.get("cron_expression") || ""),
      timezone: String(formData.get("timezone") || "UTC"),
      enabled: String(formData.get("enabled") || "true") === "true",
      max_concurrency: parseInteger(formData.get("max_concurrency"), 1)
    })
  });

  if (!response.ok) {
    return NextResponse.redirect(
      new URL("/control/execution?error=execution-schedule-failed", request.url),
      { status: 303 }
    );
  }
  return NextResponse.redirect(
    new URL("/control/execution?notice=execution-schedule-created", request.url),
    { status: 303 }
  );
}
