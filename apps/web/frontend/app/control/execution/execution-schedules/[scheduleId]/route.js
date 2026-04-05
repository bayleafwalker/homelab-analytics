// @ts-check

import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

/**
 * @param {FormDataEntryValue | null} value
 * @param {number} fallback
 */
function parseInteger(value, fallback) {
  const parsed = Number.parseInt(String(value || ""), 10);
  return Number.isNaN(parsed) ? fallback : parsed;
}

/**
 * @param {Request} request
 * @param {{ params: { scheduleId: string } }} context
 */
export async function POST(request, { params }) {
  const formData = await request.formData();
  const response = await backendRequest("patch", "/config/execution-schedules/{schedule_id}", {
    cookieHeader: request.headers.get("cookie") || "",
    params: { path: { schedule_id: params.scheduleId } },
    body: {
      schedule_id: String(formData.get("schedule_id") || params.scheduleId || ""),
      target_kind: String(formData.get("target_kind") || ""),
      target_ref: String(formData.get("target_ref") || ""),
      cron_expression: String(formData.get("cron_expression") || ""),
      timezone: String(formData.get("timezone") || "UTC"),
      enabled: String(formData.get("enabled") || "true") === "true",
      max_concurrency: parseInteger(formData.get("max_concurrency"), 1)
    }
  });

  if (!response.ok) {
    return NextResponse.redirect(
      new URL("/control/execution?error=execution-schedule-update-failed", request.url),
      { status: 303 }
    );
  }
  return NextResponse.redirect(
    new URL("/control/execution?notice=execution-schedule-updated", request.url),
    { status: 303 }
  );
}
