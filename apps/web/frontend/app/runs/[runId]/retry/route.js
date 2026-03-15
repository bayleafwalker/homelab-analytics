import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

export async function POST(request, { params }) {
  const response = await backendRequest(`/runs/${params.runId}/retry`, {
    method: "POST",
    cookieHeader: request.headers.get("cookie") || ""
  });

  if (!response.ok) {
    return NextResponse.redirect(
      new URL(`/runs/${params.runId}?error=retry-failed`, request.url),
      { status: 303 }
    );
  }

  const payload = await response.json();
  const retriedRunId = payload?.run?.run_id;
  if (!retriedRunId) {
    return NextResponse.redirect(new URL(`/runs/${params.runId}`, request.url), {
      status: 303
    });
  }
  return NextResponse.redirect(
    new URL(`/runs/${retriedRunId}?notice=retry-created&retry_of=${params.runId}`, request.url),
    { status: 303 }
  );
}
