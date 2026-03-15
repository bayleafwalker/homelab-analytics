import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

function parseOptionalInteger(value) {
  if (!value) {
    return null;
  }
  const parsed = Number.parseInt(String(value), 10);
  return Number.isNaN(parsed) ? null : parsed;
}

export async function POST(request) {
  const formData = await request.formData();
  const scheduleId = String(formData.get("schedule_id") || "") || null;
  const response = await backendRequest("/control/schedule-dispatches", {
    method: "POST",
    cookieHeader: request.headers.get("cookie") || "",
    contentType: "application/json",
    body: JSON.stringify({
      schedule_id: scheduleId,
      limit: parseOptionalInteger(formData.get("limit"))
    })
  });

  if (!response.ok) {
    return NextResponse.redirect(
      new URL("/control/execution?error=schedule-dispatch-failed", request.url),
      { status: 303 }
    );
  }

  const notice = scheduleId ? "schedule-dispatch-created" : "due-dispatches-enqueued";
  return NextResponse.redirect(
    new URL(`/control/execution?notice=${notice}`, request.url),
    { status: 303 }
  );
}
