// @ts-check

import { NextResponse } from "next/server";

import { backendJsonRequest } from "@/lib/backend";

/**
 * @param {Request} request
 * @param {{ params: { dispatchId: string } }} context
 */
export async function POST(request, { params }) {
  const { response, data } = await backendJsonRequest(
    "post",
    "/control/schedule-dispatches/{dispatch_id}/retry",
    {
      cookieHeader: request.headers.get("cookie") || "",
      params: { path: { dispatch_id: params.dispatchId } }
    }
  );

  if (!response.ok) {
    return NextResponse.redirect(
      new URL(
        `/control/execution/dispatches/${params.dispatchId}?error=schedule-dispatch-retry-failed`,
        request.url
      ),
      { status: 303 }
    );
  }

  const retriedDispatchId = data?.dispatch?.dispatch_id;
  if (!retriedDispatchId) {
    return NextResponse.redirect(
      new URL(`/control/execution/dispatches/${params.dispatchId}`, request.url),
      { status: 303 }
    );
  }

  return NextResponse.redirect(
    new URL(
      `/control/execution/dispatches/${retriedDispatchId}?notice=schedule-dispatch-retried&retry_of=${params.dispatchId}`,
      request.url
    ),
    { status: 303 }
  );
}
