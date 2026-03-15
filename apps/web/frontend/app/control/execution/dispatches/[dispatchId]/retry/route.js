import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

export async function POST(request, { params }) {
  const response = await backendRequest(
    `/control/schedule-dispatches/${params.dispatchId}/retry`,
    {
      method: "POST",
      cookieHeader: request.headers.get("cookie") || ""
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

  const payload = await response.json();
  const retriedDispatchId = payload?.dispatch?.dispatch_id;
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
