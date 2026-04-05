// @ts-check

import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

/**
 * @param {Request} request
 * @param {{ params: { publicationDefinitionId: string } }} context
 */
export async function POST(request, { params }) {
  const formData = await request.formData();
  const response = await backendRequest(
    "patch",
    "/config/publication-definitions/{publication_definition_id}/archive",
    {
      cookieHeader: request.headers.get("cookie") || "",
      params: {
        path: { publication_definition_id: params.publicationDefinitionId }
      },
      body: {
        archived: String(formData.get("archived") || "true") === "true"
      }
    }
  );

  if (!response.ok) {
    return NextResponse.redirect(
      new URL("/control/catalog?error=publication-definition-archive-failed", request.url),
      { status: 303 }
    );
  }
  return NextResponse.redirect(
    new URL("/control/catalog?notice=publication-definition-archived", request.url),
    { status: 303 }
  );
}
