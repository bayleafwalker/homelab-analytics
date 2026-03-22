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
    "/config/publication-definitions/{publication_definition_id}",
    {
      cookieHeader: request.headers.get("cookie") || "",
      params: {
        path: { publication_definition_id: params.publicationDefinitionId }
      },
      body: {
        publication_definition_id: String(
          formData.get("publication_definition_id") ||
            params.publicationDefinitionId ||
            ""
        ),
        transformation_package_id: String(
          formData.get("transformation_package_id") || ""
        ),
        publication_key: String(formData.get("publication_key") || ""),
        name: String(formData.get("name") || ""),
        description: String(formData.get("description") || "") || null
      }
    }
  );

  if (!response.ok) {
    return NextResponse.redirect(
      new URL("/control/catalog?error=publication-definition-update-failed", request.url),
      { status: 303 }
    );
  }
  return NextResponse.redirect(
    new URL("/control/catalog?notice=publication-definition-updated", request.url),
    { status: 303 }
  );
}
