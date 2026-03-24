// @ts-check

import { NextResponse } from "next/server";

import { backendJsonRequest } from "@/lib/backend";

/**
 * @param {Request} request
 * @param {{ params: { dispatchId: string } }} context
 */
export async function POST(request, { params }) {
  const { response } = await backendJsonRequest(
    "post",
    "/control/schedule-dispatches/{dispatch_id}/retry",
    {
      cookieHeader: request.headers.get("cookie") || "",
      params: { path: { dispatch_id: params.dispatchId } },
    }
  );

  if (!response.ok) {
    return NextResponse.redirect(
      new URL("/retro/control/execution?error=schedule-dispatch-retry-failed", request.url),
      { status: 303 }
    );
  }

  return NextResponse.redirect(
    new URL("/retro/control/execution?notice=schedule-dispatch-retried", request.url),
    { status: 303 }
  );
}
