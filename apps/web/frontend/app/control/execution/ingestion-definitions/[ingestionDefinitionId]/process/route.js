import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

export async function POST(request, { params }) {
  const response = await backendRequest(
    `/ingest/ingestion-definitions/${params.ingestionDefinitionId}/process`,
    {
      method: "POST",
      cookieHeader: request.headers.get("cookie") || ""
    }
  );

  if (!response.ok) {
    return NextResponse.redirect(
      new URL("/control/execution?error=ingestion-process-failed", request.url),
      { status: 303 }
    );
  }
  const payload = await response.json();
  const runId = payload?.result?.run_ids?.[0];
  return NextResponse.redirect(
    new URL(runId ? `/runs/${runId}` : "/control/execution", request.url),
    { status: 303 }
  );
}
