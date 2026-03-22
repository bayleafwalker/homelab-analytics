// @ts-check

import { NextResponse } from "next/server";

import { backendJsonRequest } from "@/lib/backend";

/**
 * @param {Request} request
 * @param {{ params: { runId: string } }} context
 */
export async function POST(request, { params }) {
  const { response, data } = await backendJsonRequest("post", "/runs/{run_id}/retry", {
    cookieHeader: request.headers.get("cookie") || "",
    params: { path: { run_id: params.runId } }
  });

  if (!response.ok) {
    return NextResponse.redirect(
      new URL(`/runs/${params.runId}?error=retry-failed`, request.url),
      { status: 303 }
    );
  }

  const retriedRunId = data?.run?.run_id;
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
