// @ts-check

import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

/**
 * @param {Request} request
 * @param {{ params: { ingestionDefinitionId: string } }} context
 */
export async function POST(request, { params }) {
  const response = await backendRequest(
    "delete",
    "/config/ingestion-definitions/{ingestion_definition_id}",
    {
      cookieHeader: request.headers.get("cookie") || "",
      params: {
        path: { ingestion_definition_id: params.ingestionDefinitionId }
      }
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
