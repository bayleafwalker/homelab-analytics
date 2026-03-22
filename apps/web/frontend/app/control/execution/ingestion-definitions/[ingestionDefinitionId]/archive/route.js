// @ts-check

import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

/**
 * @param {Request} request
 * @param {{ params: { ingestionDefinitionId: string } }} context
 */
export async function POST(request, { params }) {
  const formData = await request.formData();
  const response = await backendRequest(
    "patch",
    "/config/ingestion-definitions/{ingestion_definition_id}/archive",
    {
      cookieHeader: request.headers.get("cookie") || "",
      params: {
        path: { ingestion_definition_id: params.ingestionDefinitionId }
      },
      body: {
        archived: String(formData.get("archived") || "true") === "true"
      }
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
