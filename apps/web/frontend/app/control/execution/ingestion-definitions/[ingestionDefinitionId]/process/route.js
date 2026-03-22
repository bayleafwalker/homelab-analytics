// @ts-check

import { NextResponse } from "next/server";

import { backendJsonRequest } from "@/lib/backend";

/**
 * @param {Request} request
 * @param {{ params: { ingestionDefinitionId: string } }} context
 */
export async function POST(request, { params }) {
  const { response, data } = await backendJsonRequest(
    "post",
    "/ingest/ingestion-definitions/{ingestion_definition_id}/process",
    {
      cookieHeader: request.headers.get("cookie") || "",
      params: {
        path: { ingestion_definition_id: params.ingestionDefinitionId }
      }
    }
  );

  if (!response.ok) {
    return NextResponse.redirect(
      new URL("/control/execution?error=ingestion-process-failed", request.url),
      { status: 303 }
    );
  }
  const runId = data?.result?.run_ids?.[0];
  return NextResponse.redirect(
    new URL(runId ? `/runs/${runId}` : "/control/execution", request.url),
    { status: 303 }
  );
}
