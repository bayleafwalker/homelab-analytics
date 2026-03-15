import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

export async function POST(request, { params }) {
  const formData = await request.formData();
  const response = await backendRequest(
    `/config/ingestion-definitions/${params.ingestionDefinitionId}/archive`,
    {
      method: "PATCH",
      cookieHeader: request.headers.get("cookie") || "",
      contentType: "application/json",
      body: JSON.stringify({
        archived: String(formData.get("archived") || "true") === "true"
      })
    }
  );
  if (!response.ok) {
    return NextResponse.redirect(
      new URL("/control/execution?error=ingestion-definition-archive-failed", request.url),
      { status: 303 }
    );
  }
  return NextResponse.redirect(
    new URL("/control/execution?notice=ingestion-definition-archived", request.url),
    { status: 303 }
  );
}
