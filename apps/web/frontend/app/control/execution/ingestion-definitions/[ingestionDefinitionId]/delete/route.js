import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

export async function POST(request, { params }) {
  const response = await backendRequest(
    `/config/ingestion-definitions/${params.ingestionDefinitionId}`,
    {
      method: "DELETE",
      cookieHeader: request.headers.get("cookie") || ""
    }
  );
  if (!response.ok) {
    return NextResponse.redirect(
      new URL("/control/execution?error=ingestion-definition-delete-failed", request.url),
      { status: 303 }
    );
  }
  return NextResponse.redirect(
    new URL("/control/execution?notice=ingestion-definition-deleted", request.url),
    { status: 303 }
  );
}
