// @ts-check

import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

/**
 * @param {Request} request
 * @param {{ params: { scheduleId: string } }} context
 */
export async function POST(request, { params }) {
  const formData = await request.formData();
  const response = await backendRequest(
    "patch",
    "/config/execution-schedules/{schedule_id}/archive",
    {
      cookieHeader: request.headers.get("cookie") || "",
      params: { path: { schedule_id: params.scheduleId } },
      body: {
        archived: String(formData.get("archived") || "true") === "true"
      }
    }
  );
  if (!response.ok) {
    return NextResponse.redirect(
      new URL("/control/execution?error=execution-schedule-archive-failed", request.url),
      { status: 303 }
    );
  }
  return NextResponse.redirect(
    new URL("/control/execution?notice=execution-schedule-archived", request.url),
    { status: 303 }
  );
}
